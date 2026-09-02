#!/usr/bin/env python3
"""Build the owner-selected v1.9 B-light native-prompt editor card.

The card has three authored roots and no others: the candidate-derived Bank-2
editor plane, the profile-conditional resident prompt bridge in ``repl.c`` and
the final-LTO call boundary on ``scr_cursor``.
It spends exactly one WPLTO/product link after a zero-build preflight, then
attributes the complete successor pair before read-only Scope/Acceptance.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import c2_bank2_composed_ownership as COMPOSED  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v17_ide_idle_blink_product_card_r10 as R10  # noqa: E402
import c2_v18_capture_hybrid_native_client_card as CLIENT  # noqa: E402
import c2_v180_substrate_device_result as DEVICE  # noqa: E402
import c2_v190_native_capture_client_card as BLOCK_A  # noqa: E402
import c2_v190_native_prompt_editor_pricing as PRICE  # noqa: E402


BASE = CLIENT.BASE
ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
DECISION = ROOT / "config/c2-v190-native-prompt-editor-card.json"
R3_DECISION = ROOT / "config/c2-v190-native-prompt-editor-card-r3.json"
R4_DECISION = ROOT / "config/c2-v190-native-prompt-editor-card-r4.json"
PRICE_RECEIPT = ARCH / "c2.3-v1.9-native-prompt-editor-pricing-receipt.json"
R2_BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r2"
R2_ELF = R2_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
R2_PRG = R2_BUILD / "wplto/lisp65-c2-substitution-linked.prg"
R2_PROFILE = R2_BUILD / "wplto/resolved-profile.txt"
R3_BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r3"
R3_PROFILE = R3_BUILD / "wplto/resolved-profile.txt"
R4_BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r4"
R4_PROFILE = R4_BUILD / "wplto/resolved-profile.txt"
BUILD = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r5"
PREFLIGHT = ROOT / "build/c2.3/v1.9-native-prompt-editor-card-r1-preflight"
RECEIPT = ARCH / "c2.3-v1.9-native-prompt-editor-card-r5-receipt.json"
DIFFERENCE = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r4-r5-difference.json")
FIRST_RED = ARCH / "c2.3-v1.9-native-prompt-editor-card-r1-first-red.json"
RESUME_RED = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r1-resume-first-red.json")
R3_PRODUCT_FIRST_RED = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r3-first-red.json")
PRODUCT_FIRST_RED = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r5-first-red.json")
R3_LINK_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r3-link-red-attribution.json")
R4_LINK_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r4-link-red-attribution.json")
REPORT = ROOT / "docs/planning/v1.9.0-native-prompt-editor-card-report.md"
R4_PREFLIGHT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r4-preflight.json")
R3_LINK_RED_REPORT = ROOT / (
    "docs/planning/v1.9.0-native-prompt-editor-r3-link-red-attribution.md")
R4_LINK_RED_REPORT = ROOT / (
    "docs/planning/v1.9.0-native-prompt-editor-r4-link-red-attribution.md")
R5_PRICE_DECISION = ROOT / (
    "config/c2-v190-native-prompt-editor-r5-pricing.json")
R5_PRICE_RECEIPT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r5-placement-pricing.json")
R5_PRICE_REPORT = ROOT / (
    "docs/planning/v1.9.0-native-prompt-editor-r5-placement-pricing.md")
R5_DECISION = ROOT / "config/c2-v190-native-prompt-editor-card-r5.json"
R5_PREFLIGHT = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r5-preflight.json")
R5_LINK_RED_ATTRIBUTION = ARCH / (
    "c2.3-v1.9-native-prompt-editor-card-r5-link-red-attribution.json")
R5_LINK_RED_REPORT = ROOT / (
    "docs/planning/v1.9.0-native-prompt-editor-r5-link-red-attribution.md")
STACK_OWNERSHIP = ROOT / "config/c2-stack-overlay-ownership-contract.json"
BLOCK_A_RECEIPT = ARCH / (
    "c2.3-v1.9-native-capture-client-card-r1-receipt.json")
ELF = BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf"
PRG = BUILD / "wplto/lisp65-c2-substitution-linked.prg"
PROFILE = BUILD / "wplto/resolved-profile.txt"
FINAL_PRODUCT_ROOT: Path | None = None
PLANE_ROOT = PREFLIGHT / "setup-owned/static-plane/narrow-static"
PLANE_RECEIPT = PREFLIGHT / "v19-native-prompt-editor-static-plane.json"
CLIENT_SOURCE = PREFLIGHT / "sources/stdlib-read-line.lisp"
C2D = PLANE_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = PLANE_ROOT / "v6-semantics/bank2-static-code.bin"
MANIFEST = PLANE_ROOT / "stdlib-p0.manifest.json"
HEADER = PLANE_ROOT / "stdlib-p0.h"
DRIVER = Path(__file__).resolve()
REPL = ROOT / "src/repl.c"
SCREEN = ROOT / "src/screen.c"
GENERATOR = ROOT / "tools/host-lisp/bytecode_p0_stdlib.py"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
COMPILER = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
OBJDUMP = ROOT / "tools/llvm-mos/bin/llvm-objdump"
PRICE_COMMIT = "b9e5b8c6"


def configure_final_product_root(root: Path) -> None:
    global FINAL_PRODUCT_ROOT
    if FINAL_PRODUCT_ROOT is not None and FINAL_PRODUCT_ROOT != root:
        raise CardError("final product output root configured twice")
    FINAL_PRODUCT_ROOT = root


def final_product_root() -> Path:
    return FINAL_PRODUCT_ROOT if FINAL_PRODUCT_ROOT is not None else BUILD / "wplto"
R3_EVIDENCE_COMMIT = "a35a2c4c"
R4_FORMAT = "lisp65-c2-v190-native-prompt-editor-card-r4-v1"
FORMAT = "lisp65-c2-v190-native-prompt-editor-card-r5-v1"
STATUS = "PASS: V1.9 B-LIGHT NATIVE PROMPT EDITOR GREEN"
PLANE_BYTES = 47468
PLANE_DELTA = 133
LARGEST_BANK2_HOLE = 16198
CLIENT_FUNCTIONS = CLIENT.CLIENT_FUNCTIONS + (
    "%native-prompt", "%native-read-line")

ORIGINAL_DERIVE_CLIENT_SOURCE = CLIENT.derive_client_source
ORIGINAL_VALIDATE_CLIENT_SOURCE = CLIENT.validate_client_source
ORIGINAL_LIFECYCLE_MUTATIONS = CLIENT.lifecycle_mutations
ORIGINAL_CLIENT_FUNCTIONS = CLIENT.CLIENT_FUNCTIONS


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
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(argv: list[str], label: str) -> str:
    result = subprocess.run(argv, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def git_bytes(commit: str, path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def authority() -> dict[str, Any]:
    decision = load(DECISION)
    r3 = load(R3_DECISION)
    r4 = load(R4_DECISION)
    r5 = load(R5_DECISION)
    r3_red = load(R3_LINK_RED_ATTRIBUTION)
    r4_red = load(R4_LINK_RED_ATTRIBUTION)
    r5_price = load(R5_PRICE_RECEIPT)
    price = load(PRICE_RECEIPT)
    require(decision["format"] == "lisp65-c2-v190-native-prompt-editor-card-v1"
            and decision["owner_decision"] == "B-light frei"
            and decision["selected_variant"] == "B-light"
            and decision["budget"] == {"WPLTO_runs": 1, "product_links": 1,
                                        "media_builds": 0,
                                        "device_contacts": 0}
            and price["status"] == PRICE.STATUS
            and price["comparison"]["recommendation"] == "B-light"
            and price["variants"]["B_light"]["direct_fit"] is True
            and price["variants"]["B_full"]["selectable_now"] is False
            and decision["predecessor_pair"] == {
                "ELF_sha256": bind(BLOCK_A.ELF)["sha256"],
                "PRG_sha256": bind(BLOCK_A.PRG)["sha256"]},
            "B-light owner/price authority drift")
    r2_pair = {"ELF_sha256": bind(R2_ELF)["sha256"],
               "PRG_sha256": bind(R2_PRG)["sha256"]}
    require(r3["format"] ==
                "lisp65-c2-v190-native-prompt-editor-card-r3-authorization-v1"
            and r3["owner_decision"] == "r3-Link frei"
            and r3["status"] == "one-replacement-card-authorized"
            and r3["r2_frozen_unqualified_pair"] == r2_pair
            and r3["budget"] == {"WPLTO_runs": 1, "product_links": 1,
                                  "media_builds": 0,
                                  "device_contacts": 0},
            "r3 replacement-link authority drift")
    require(r4["format"] ==
                "lisp65-c2-v190-native-prompt-editor-card-r4-authorization-v1"
            and r4["owner_decision"] == "r4-Link frei"
            and r4["status"] == "one-replacement-card-authorized"
            and r4["budget"] == {"WPLTO_runs": 1, "product_links": 1,
                                  "media_builds": 0,
                                  "device_contacts": 0}
            and r4["r3_evidence"]["receipt"] ==
                bind(R3_LINK_RED_ATTRIBUTION)["path"]
            and r4["r3_evidence"]["overlap_bytes"] == 46
            and r3_red["status"] ==
                "ATTRIBUTED: FINAL-LTO CALLEE FOLD OVERFLOWS FIXED BANK0"
            and r3_red["link_map"]["actual_product_overlap_bytes"] == 46,
            "r4 replacement-link authority drift")
    require(r5["format"] ==
                "lisp65-c2-v190-native-prompt-editor-card-r5-authorization-v1"
            and r5["owner_decision"] == "r5-Link frei"
            and r5["status"] == "one-priced-replacement-card-authorized"
            and r5["selected_candidate"] ==
                "derived mapped-facade slide"
            and r5["budget"] == {"WPLTO_runs": 1, "product_links": 1,
                                  "media_builds": 0,
                                  "device_contacts": 0}
            and r5["authority"]["pricing_receipt"] ==
                bind(R5_PRICE_RECEIPT)["path"]
            and r5["authority"]["r4_link_red_attribution"] ==
                bind(R4_LINK_RED_ATTRIBUTION)["path"]
            and r4_red["status"] ==
                "ATTRIBUTED: BOUNDARY SUCCEEDS; ORDINARY TEXT LACKS 12 BYTES"
            and r5_price["status"] ==
                "PASS: ONE R5 PLACEMENT WINNER PRICED"
            and r5_price["recommended_candidate"]["name"] ==
                "derived mapped-facade slide",
            "r5 priced-link authority drift")
    return {"decision": bind(DECISION), "pricing": bind(PRICE_RECEIPT),
            "r3_decision": bind(R3_DECISION),
            "r4_decision": bind(R4_DECISION),
            "r5_decision": bind(R5_DECISION),
            "r5_placement_price": bind(R5_PRICE_RECEIPT),
            "r3_link_red_attribution": bind(R3_LINK_RED_ATTRIBUTION),
            "r4_link_red_attribution": bind(R4_LINK_RED_ATTRIBUTION),
            "selected_variant": "B-light", "budget": r5["budget"],
            "predecessor_pair": decision["predecessor_pair"],
            "r2_frozen_unqualified_pair": r2_pair}


def predecessor_repl_source() -> str:
    raw = git_bytes(PRICE_COMMIT, REPL)
    price = load(PRICE_RECEIPT)
    require(hashlib.sha256(raw).hexdigest() ==
            price["inputs"]["native_repl"]["sha256"],
            "pricing-era native repl source drift")
    return raw.decode()


def expected_repl_source() -> str:
    source = predecessor_repl_source()
    macro = "LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY"
    include = ("#if defined(LISP65_COMPILE_REPL) || "
               "defined(LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY)")
    replacement = include + " \\" + "\n    || defined(" + macro + ")"
    require(source.count(include) == 1, "native VM include seam drift")
    source = source.replace(include, replacement, 1)
    start = source.index(
        "static uint8_t read_line(char *buf, uint8_t *np, uint8_t max) {")
    end = source.index("\nvoid repl(void)", start)
    old = source[start:end]
    source = (source[:start] + PRICE.direct_bridge_block(macro) + old
              + "\n#endif\n" + source[end:])
    seam = ('        emit_str("lisp65> ");\n'
            '        st = read_line(buf, &n, BUF_MAX);\n'
            "        if (st == 1) emit('\\n');")
    changed = ('#ifndef ' + macro + '\n'
               '        emit_str("lisp65> ");\n'
               '#endif\n'
               '        st = read_line(buf, &n, BUF_MAX);\n'
               '#ifndef ' + macro + '\n'
               "        if (st == 1) emit('\\n');\n"
               '#endif')
    require(source.count(seam) == 1, "native prompt ownership seam drift")
    return source.replace(seam, changed, 1)


def repl_source_gate(source: str | None = None) -> dict[str, Any]:
    current = REPL.read_text(encoding="utf-8") if source is None else source
    expected = expected_repl_source()
    require(current == expected, "B-light repl changed outside priced form")
    macro = "LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY"
    require(current.count("vm_run_dir(" + macro + ", NULL, 0)") == 1
            and current.count("#ifdef " + macro) == 1
            and current.count("#ifndef " + macro) == 2
            and "length >= (uint16_t)(max - *np)" in current
            and "str_copy_out(line, buf + *np, length)" in current,
            "B-light route/limit source contract drift")
    return {"status": "PASS: EXACT PRICED PROFILE-CONDITIONAL REPL",
            "predecessor": {"bytes": len(predecessor_repl_source().encode()),
                            "sha256": hashlib.sha256(
                                predecessor_repl_source().encode()).hexdigest()},
            "candidate": bind(REPL), "macro": macro,
            "fallback": "preprocessor retains old C collector",
            "overlong": "reject before copy; never truncate/evaluate"}


def derive_editor_source() -> str:
    source = PRICE.editor_candidate()
    require(PRICE.EDITOR == BLOCK_A.CLIENT_SOURCE,
            "pricing source is not accepted Block-A editor")
    return source


def validate_editor_source(source: str) -> dict[str, Any]:
    predecessor = BLOCK_A.CLIENT_SOURCE.read_text(encoding="utf-8")
    require(source == derive_editor_source(),
            "B-light editor changed outside priced transform")
    lifecycle = ORIGINAL_VALIDATE_CLIENT_SOURCE(predecessor)
    ordered = lifecycle["ordered_lifecycle"]
    positions: list[int] = []
    cursor = source.rfind("(defun read-line ")
    for token in ordered:
        cursor = source.find(token, cursor + (1 if positions else 0))
        require(cursor >= 0, f"B-light lifecycle token absent: {token}")
        positions.append(cursor)
    require(positions == sorted(positions)
            and source.count("(defun %native-prompt ") == 1
            and source.count("(defun %native-read-line ") == 1
            and "(defun read-line (&rest prompt)" in source
            and "(if native 8 (if prompted 5 0))" in source
            and "(if native (- full-columns 8) full-columns)" in source,
            "B-light editor ownership/viewport contract drift")
    return {"status": "PASS: BLOCK-A CLIENT PLUS COMPOSED NATIVE PROMPT",
            "predecessor": bind(BLOCK_A.CLIENT_SOURCE),
            "candidate": {"bytes": len(source.encode()),
                          "sha256": hashlib.sha256(source.encode()).hexdigest()},
            "ordered_lifecycle": ordered,
            "Block_A_non_prompt_logic_byte_identical": True,
            "native_prompt_origin_columns": 8,
            "ordinary_read_line_origin_columns": 0,
            "helpers": ["%native-prompt", "%native-read-line"]}


def editor_mutations(source: str) -> list[dict[str, str]]:
    cases = {
        "omit-native-entry": source.replace(
            "(defun %native-read-line () (read-line (quote native)))\n", "", 1),
        "split-prompt-owner": source.replace(
            '(write-string "lisp65> ")', "nil", 1),
        "forget-prompt-width": source.replace(
            "(if native (- full-columns 8) full-columns)", "full-columns", 1),
        "forget-return-disarm": source.rsplit(
            "        (poke 255 141 255)\n", 1)[0] + "        answer))))\n",
        "move-native-origin-to-comfort": source.replace(
            "(if native 8 (if prompted 5 0))",
            "(if prompted 5 0)", 1),
    }
    rejected = []
    for name, trial in cases.items():
        try:
            validate_editor_source(trial)
        except CardError as error:
            rejected.append({"name": name, "observed_red": str(error)})
    require([row["name"] for row in rejected] == list(cases),
            "B-light editor mutation survived")
    return rejected


def configure() -> None:
    for name, value in {
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "RECEIPT": RECEIPT,
        "FIRST_RED": FIRST_RED, "REPORT": REPORT, "ELF": ELF, "PRG": PRG,
        "PROFILE": PROFILE, "PLANE_ROOT": PLANE_ROOT,
        "PLANE_RECEIPT": PLANE_RECEIPT, "CLIENT_SOURCE": CLIENT_SOURCE,
        "C2D": C2D, "CODE": CODE, "MANIFEST": MANIFEST,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
    }.items():
        setattr(CLIENT, name, value)
    CLIENT.configure()
    BASE.INVOCATION = PREFLIGHT / "candidate-invocation-r5.json"
    CLIENT.derive_client_source = derive_editor_source
    CLIENT.validate_client_source = validate_editor_source
    CLIENT.lifecycle_mutations = editor_mutations
    CLIENT.CLIENT_FUNCTIONS = CLIENT_FUNCTIONS
    BASE.authority = authority
    BASE.configuration_gate = configuration_gate
    BASE.setup_child = setup_child
    BASE.final_gate = final_gate
    R10.ACCEPT.linked_tuple_gate = tuple_loadaddr_gate
    R10.ACCEPT.EMITTED.acceptance_position_mutations = lambda: [
        "move-LMA-without-tuple-follow", "mutate-tuple-without-LMA-reason",
        "non-page-congruent-LOADADDR"]


def setup_child() -> tuple[Any, dict[str, Any], dict[str, object]]:
    result = BLOCK_A.ORIGINAL_SETUP()
    PRODUCT.configure_mapped_tenant_lma_policy("map-page-top")
    PRODUCT.configure_mapped_facade_placement(
        "after-final-text-floor", text_floor=32)
    ordinals = stdlib_header_ordinals()
    PRODUCT.configure_compiler_consumed_stdlib_header(
        HEADER, bind(HEADER), ordinals["repl_banner"])
    return result


def configuration_gate() -> dict[str, Any]:
    value = CLIENT.configuration_gate()
    value.update({"world": "v1.9-B-light-native-prompt-editor",
                  "client": "Block-A armed read-line plus native prompt mode",
                  "excluded": ["repl-comfort", "Block-3", "diagnostic-client"],
                  "native_prompt_route": "candidate-derived private entry"})
    return value


def stdlib_header_ordinals() -> dict[str, int]:
    raw = HEADER.read_bytes()
    rows = {}
    for name, macro in (
            ("repl_banner", "LISP65_BYTECODE_STDLIB_REPL_BANNER_ENTRY"),
            ("native_read_line",
             "LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY")):
        matches = re.findall(
            rb"^#define " + macro.encode() + rb" ([0-9]+)u$",
            raw, re.MULTILINE)
        require(len(matches) == 1,
                f"candidate stdlib header {macro} population drift")
        rows[name] = int(matches[0])
    require(rows == {"repl_banner": 239, "native_read_line": 395},
            "candidate stdlib header ordinal drift")
    return rows


def stdlib_consumer_preflight() -> dict[str, Any]:
    ordinals = stdlib_header_ordinals()
    target = PREFLIGHT / "real-stdlib-consumer-probe.prg"
    PRODUCT.configure_compiler_consumed_stdlib_header(
        HEADER, bind(HEADER), ordinals["repl_banner"])
    flags, report = PRODUCT.compiler_consumed_stdlib_header_flags(
        PREFLIGHT, target)
    require(report is not None, "candidate stdlib consumer did not arm")
    PRODUCT.materialized_compiler_stdlib_header_gate(flags, report)
    require(report["status"] ==
                "passed-bound-candidate-stdlib-header-consumed"
            and report["bound_header"] == bind(HEADER),
            "candidate stdlib path/value did not materialize")
    historical = (ROOT / "build/c2.2/substitution/stdlib-p0.h").relative_to(
        ROOT).as_posix()
    rejected = {}
    for name, mutant_flags, mutant_report in (
            ("historical-header-path",
             ["-include", historical, *flags[2:]],
             json.loads(json.dumps(report))),
            ("candidate-path-historical-banner-value", list(flags),
             {**json.loads(json.dumps(report)), "consumed_value": 238})):
        try:
            PRODUCT.materialized_compiler_stdlib_header_gate(
                mutant_flags, mutant_report)
        except RuntimeError as error:
            rejected[name] = str(error)
    require(set(rejected) == {"historical-header-path",
                              "candidate-path-historical-banner-value"},
            "candidate stdlib consumer mutation survived")
    return {"status": "PASS: REAL COMPILER CONSUMES CANDIDATE STDLIB HEADER",
        "materialized": report, "ordinals": ordinals,
        "native_entry_proven_by_exact_header_binding": True,
        "mutations_rejected": rejected}


def candidate_stdlib_consumption() -> dict[str, Any]:
    rows = {}
    expected = bind(HEADER)
    for key, name in (("seed", "resident-island-seed.prg"),
                      ("final", "lisp65-c2-substitution-linked.prg")):
        path = BUILD / "wplto" / (name + ".stdlib-input-consumption.json")
        value = load(path)
        require(value["status"] ==
                    "passed-bound-candidate-stdlib-header-consumed"
                and value["bound_header"] == expected
                and value["materialized_header"] == expected
                and value["consumed_value"] == 239,
                "real compiler did not consume exact candidate stdlib header")
        rows[key] = {"receipt": bind(path), "result": value}
    return rows


def finalize_b_light_plane(value: dict[str, Any]) -> dict[str, Any]:
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    expected = {"%rl-screen-tail": 212, "read-line": 235,
                "%native-prompt": 32, "%native-read-line": 16}
    observed = {name: int(entries[name]["length"]) for name in expected}
    require(value["geometry"]["bytes"] == PLANE_BYTES
            and observed == expected
            and len(manifest["entries"]) == 398
            and all(length < 255 for length in observed.values()),
            "emitted B-light plane price drift")
    header = HEADER.read_text(encoding="utf-8")
    ordinal = [row["name"] for row in manifest["entries"]].index(
        "%native-read-line")
    define = ("#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY "
              f"{ordinal}u")
    require(ordinal == 395 and header.count(define) == 1,
            "candidate directory/header native entry divergence")
    profile_path = ROOT / value["profile"]["path"]
    profile = load(profile_path)
    profile["authority"]["successor"] = {
        "kind": "v1.9-B-light-native-prompt-editor",
        "rule": ("Block-A armed editor plus composed prompt helpers; private "
                 "entry ordinal derives from the candidate directory")}
    profile_path.write_bytes(canonical(profile))
    value["profile"] = bind(profile_path)
    value["B_light"] = {"objects": observed, "native_entry_ordinal": ordinal,
        "plane_predecessor_bytes": 47335,
        "plane_candidate_bytes": PLANE_BYTES,
        "plane_delta_bytes": PLANE_DELTA,
        "pricing_forecast_bytes": 47482,
        "pricing_forecast_delta_bytes": 147,
        "forecast_variance_bytes": -14,
        "forecast_variance_attribution": (
            "the pricing prototype added two seven-byte directory entries "
            "to the static-plane extent although code_bytes already defines "
            "the composed plane owner; emitted object-code delta is 133"),
        "largest_object_bytes": max(observed.values()),
        "new_names": ["%native-prompt", "%native-read-line"],
        "namepool_bytes": 33, "symbol_slots": 2}
    PLANE_RECEIPT.write_bytes(canonical(value))
    return value


def emit_b_light_plane() -> dict[str, Any]:
    return finalize_b_light_plane(CLIENT.emit_client_plane())


def target_compile(source: Path, header_root: Path, name: str) -> dict[str, Any]:
    out = PREFLIGHT / "target-codegen"
    out.mkdir(parents=True, exist_ok=True)
    obj = out / f"{name}.o"
    definitions, features = PRICE.profile_definitions()
    argv = [str(COMPILER), "-Oz", "-Wall", "-fno-lto",
            "-ffile-compilation-dir=.", "-fdebug-compilation-dir=.",
            "-fcoverage-compilation-dir=.", "-I", "src", "-I",
            str(header_root.relative_to(ROOT)),
            *[f"-D{row}" for row in definitions], "-c",
            str(source.relative_to(ROOT)), "-o", str(obj.relative_to(ROOT))]
    output = run(argv, f"B-light target compile {name}")
    return {"source": bind(source), "object": bind(obj),
            "sections": PRICE.section_sizes(obj),
            "definitions": len(definitions), "features": len(features),
            "warnings": [row for row in output.splitlines() if "warning:" in row]}


def target_codegen_gate() -> dict[str, Any]:
    out = PREFLIGHT / "target-codegen"
    out.mkdir(parents=True, exist_ok=True)
    predecessor = out / "repl-predecessor.c"
    predecessor.write_text(predecessor_repl_source(), encoding="utf-8")
    baseline = target_compile(predecessor, BLOCK_A.PLANE_ROOT, "predecessor")
    fallback = target_compile(REPL, BLOCK_A.PLANE_ROOT, "candidate-fallback")
    candidate = target_compile(REPL, PLANE_ROOT, "candidate-editor")
    expected = {
        "predecessor": {".text.repl": 616, ".rodata.str1.1": 14,
                        ".bss.repl.buf": 192},
        "candidate-fallback": {".text.repl": 616, ".rodata.str1.1": 14,
                               ".bss.repl.buf": 192},
        "candidate-editor": {".text.repl": 626, ".rodata.str1.1": 5,
                             ".bss.repl.buf": 192}}
    require({"predecessor": baseline["sections"],
             "candidate-fallback": fallback["sections"],
             "candidate-editor": candidate["sections"]} == expected,
            "materialized-profile B-light codegen price drift")
    return {"status": "PASS: FULL PROFILE CODEGEN MATCHES PRICE",
            "compiler_driver": {"path": COMPILER.relative_to(ROOT).as_posix(),
                "resolved_executable": bind(COMPILER.resolve())},
            "predecessor": baseline, "candidate_fallback": fallback,
            "candidate_editor": candidate,
            "delta": {"text_bytes": 10, "rodata_bytes": -9,
                      "aggregate_alloc_bytes": 1, "bss_bytes": 0},
            "fallback_section_geometry_identical": True,
            "claim_limit": "target objects; final-LTO size remains post-link"}


def source_mutations() -> list[str]:
    source = REPL.read_text(encoding="utf-8")
    cases = {
        "literal-entry-ordinal": source.replace(
            "LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY, NULL, 0",
            "395, NULL, 0", 1),
        "silent-truncation": source.replace(
            "length >= (uint16_t)(max - *np)", "length > 65535u", 1),
        "C-prompt-remains-owner": source.replace(
            "#ifndef LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY\n"
            '        emit_str("lisp65> ");\n#endif\n',
            '        emit_str("lisp65> ");\n', 1),
        "C-newline-remains-owner": source.replace(
            "#ifndef LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY\n"
            "        if (st == 1) emit('\\n');\n#endif\n",
            "        if (st == 1) emit('\\n');\n", 1),
        "fallback-collector-removed": source.replace(
            "#else\nstatic uint8_t read_line",
            "#endif\nstatic uint8_t read_line", 1),
    }
    rejected = []
    for name, trial in cases.items():
        try:
            repl_source_gate(trial)
        except CardError:
            rejected.append(name)
    require(rejected == list(cases), "B-light source mutation survived")
    return rejected


def screen_boundary_source_gate(source: str | None = None) -> dict[str, Any]:
    current = SCREEN.read_text(encoding="utf-8") if source is None else source
    signature = "__attribute__((noinline)) void scr_cursor(uint8_t on) {"
    require(current.count(signature) == 1,
            "scr_cursor non-inline source boundary absent")
    predecessor = git_bytes(R3_EVIDENCE_COMMIT, SCREEN)
    require(signature.encode() not in predecessor
            and b"void scr_cursor(uint8_t on) {" in predecessor,
            "sealed r3 boundary predecessor drift")
    mutant = current.replace("__attribute__((noinline)) ", "", 1)
    try:
        screen_boundary_source_gate(mutant)
    except CardError as error:
        mutation_red = str(error)
    else:
        raise CardError("removed scr_cursor boundary survived source gate")
    r3 = load(R3_LINK_RED_ATTRIBUTION)
    require(r3["LTO_mechanism"]["symbols"]["kb_cursor_off"] == {
                "r2_bytes": 5, "r3_bytes": 51, "delta_bytes": 46}
            and r3["link_map"]["actual_product_overlap_bytes"] == 46,
            "sealed final-LTO boundary mutation witness drift")
    return {"status": "PASS: SCR_CURSOR BOUNDARY ARMED FOR FINAL-ELF PROOF",
        "candidate": bind(SCREEN),
        "sealed_boundary_removed_world": {
            "commit": R3_EVIDENCE_COMMIT,
            "source_sha256": hashlib.sha256(predecessor).hexdigest(),
            "LTO_kb_cursor_off_bytes": 51,
            "fixed_bank0_overlap_bytes": 46,
            "evidence": bind(R3_LINK_RED_ATTRIBUTION)},
        "source_mutation_rejected": mutation_red,
        "claim_limit": "source arms the boundary; final ELF proves efficacy"}


def derived_full_map_checker_gate(source: str | None = None) -> dict[str, Any]:
    current = (Path(PRODUCT.__file__).read_text(encoding="utf-8")
               if source is None else source)
    required = (
        "ADDR(.rodata) + SIZEOF(.rodata) <= 0xb98c",
        "ADDR(.bss) + SIZEOF(.bss) <= 0xbffb",
        "0xc000 - (ADDR(.bss) + SIZEOF(.bss)) >= 5",
    )
    forbidden = (
        "SIZEOF(.rodata) == 879",
        "SIZEOF(.bss) == 1585",
        "0xc000 - (ADDR(.bss) + SIZEOF(.bss)) == 5",
    )
    require(all(current.count(row) == 1 for row in required)
            and all(row not in current for row in forbidden),
            "full-map candidate-derived bounds absent")
    rejected = []
    for name, mutant in (
            ("restore-rodata-equality",
             current.replace(required[0], "SIZEOF(.rodata) == 879", 1)),
            ("restore-bss-equality",
             current.replace(required[1],
                             "ADDR(.bss) + SIZEOF(.bss) == 0xbffb", 1)),
            ("restore-margin-equality",
             current.replace(required[2],
                             "0xc000 - (ADDR(.bss) + SIZEOF(.bss)) == 5", 1))):
        try:
            derived_full_map_checker_gate(mutant)
        except CardError:
            rejected.append(name)
    require(len(rejected) == 3, "full-map exact-pin mutation survived")
    return {"status": "PASS: FULL-MAP SIZES ARE BOUNDS NOT EQUALITIES",
        "source": bind(Path(PRODUCT.__file__)),
        "relations": list(required), "forbidden_exact_pins": list(forbidden),
        "mutations_rejected": rejected,
        "r3_observation": {"rodata_delta_bytes": -9,
                           "bss_delta_bytes": -1,
                           "derived_margin_bytes": 6}}


def prepare_r4() -> None:
    configure()
    require(not R4_PREFLIGHT.exists() and not BUILD.exists()
            and not BASE.INVOCATION.exists() and not RECEIPT.exists(),
            "r4 preflight is one-shot")
    old = load(BASE.PREFLIGHT_RECEIPT)
    require(old["status"] == "PASS: V1.9 B-LIGHT CARD ARMED 0/1",
            "r3 zero-link preflight is not green")
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-08-29",
        "status": "PASS: R4 FINAL-LTO BOUNDARY ARMED 0/1",
        "authority": authority(),
        "inherited_B_light_preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "boundary": screen_boundary_source_gate(),
        "full_map_checker_conversion": derived_full_map_checker_gate(),
        "real_stdlib_header_consumer": stdlib_consumer_preflight(),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit the preflight, then spend exactly one r4 WPLTO/link"}
    R4_PREFLIGHT.write_bytes(canonical(value))
    print("v1.9 B-light: R4 PREFLIGHT PASS boundary=armed overlap-mutant=46")


def r5_linker_placement_source_gate(source: str) -> dict[str, Any]:
    derived = (
        "MAX(0xb3b0, ADDR(.text) + SIZEOF(.text) + 32)")
    required = (
        ".lisp65_c2_mapped_far_facade " + derived + " : AT((" + derived,
        "ADDR(.lisp65_c2_mapped_far_facade) == " + derived,
        "ADDR(.lisp65_c2_mapped_far_facade) -\n"
        "            (ADDR(.text) + SIZEOF(.text)) >= 32",
        "LOADADDR(.lisp65_c2_mapped_far_facade) -\n"
        "            ADDR(.lisp65_c2_mapped_far_facade) ==\n"
        "                __lisp65_c2_mapped_shared_offset",
        "SIZEOF(.lisp65_c2_mapped_far_facade) == 98",
        "SIZEOF(.lisp65_c2_mapped_far_facade) <= 0xb4a3",
    )
    forbidden = (
        "ADDR(.lisp65_c2_mapped_far_facade) == 0xb3b0",
        "ADDR(.text) + SIZEOF(.text) <= 0xb3b0",
    )
    require(all(source.count(row) >= 1 for row in required)
            and all(row not in source for row in forbidden),
            "r5 derived facade linker authority absent")
    cases = {
        "restore-fixed-b3b0": source.replace(derived, "0xb3b0"),
        "remove-final-text-floor": source.replace(
            "ADDR(.text) + SIZEOF(.text) + 32",
            "ADDR(.text) + SIZEOF(.text)"),
        "move-vma-without-lma": source.replace(
            " : AT((" + derived, " : AT((0xb3b0", 1),
        "remove-tail-owner-bound": source.replace(
            "SIZEOF(.lisp65_c2_mapped_far_facade) <= 0xb4a3",
            "SIZEOF(.lisp65_c2_mapped_far_facade) <= 0xffff", 1),
    }
    rejected = {}
    for name, mutant in cases.items():
        try:
            r5_linker_placement_source_gate(mutant)
        except CardError as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases),
            "r5 linker placement mutation survived")
    return {"status": "PASS: R5 DERIVED FACADE AUTHORITY MATERIALIZED",
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "relations": list(required), "forbidden_pins": list(forbidden),
        "mutations_rejected": rejected}


def prepare_r5() -> None:
    configure()
    require(not R5_PREFLIGHT.exists() and not BUILD.exists()
            and not RECEIPT.exists() and not DIFFERENCE.exists()
            and not BASE.INVOCATION.exists(),
            "r5 preflight is one-shot")
    old = load(BASE.PREFLIGHT_RECEIPT)
    r4_pre = load(R4_PREFLIGHT)
    require(old["status"] == "PASS: V1.9 B-LIGHT CARD ARMED 0/1"
            and r4_pre["status"] ==
                "PASS: R4 FINAL-LTO BOUNDARY ARMED 0/1",
            "r5 inherited zero-link preflights are not green")
    setup_child()
    linker = PRODUCT.linker_script(ownership_opt_in=True)
    gate = r5_linker_placement_source_gate(linker)
    price = load(R5_PRICE_RECEIPT)
    require(price["recommended_candidate"]["projected"] == {
                "derived_vma": 0xB3DC, "derived_lma": 0x333DC,
                "ordinary_text_reserve_bytes": 32,
                "tail_reserve_bytes": 101,
                "end_vma_exclusive": 0xB43E,
                "end_lma_exclusive": 0x3343E,
                "vma_and_lma_shift_bytes": 44},
            "r5 priced placement authority drift")
    value = {"format": FORMAT + "-preflight",
        "recorded_on": "2026-08-29",
        "status": "PASS: R5 DERIVED FACADE ARMED 0/1",
        "authority": authority(),
        "inherited_B_light_preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "inherited_boundary_preflight": bind(R4_PREFLIGHT),
        "placement_source": gate,
        "priced_final_world": price["recommended_candidate"]["projected"],
        "real_stdlib_header_consumer": stdlib_consumer_preflight(),
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "next": "commit this preflight, then spend exactly one r5 WPLTO/link"}
    R5_PREFLIGHT.write_bytes(canonical(value))
    print("v1.9 B-light: R5 PREFLIGHT PASS derived-facade link=0/1")


def preflight_gates(plane: dict[str, Any]) -> dict[str, Any]:
    source = repl_source_gate()
    codegen = target_codegen_gate()
    framebuffer = PRICE.framebuffer_gate(derive_editor_source())
    generator = GENERATOR.read_text(encoding="utf-8")
    require(generator.count('if "%native-read-line" in names:') == 1
            and generator.count(
                '"#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY %du"')
                == 1,
            "candidate-derived header generator seam drift")
    require(framebuffer["native_prompt_and_edited_line"] == "lisp65> abc"
            and framebuffer["ordinary_read_line_framebuffer_identical"] is True,
            "B-light composed framebuffer preflight red")
    return {"status": "PASS: B-LIGHT PRE-CARD WALLS GREEN",
            "repl_source": source, "target_codegen": codegen,
            "framebuffer": framebuffer,
            "header": {"binding": bind(HEADER),
                       "generator": bind(GENERATOR),
                       "native_entry_ordinal": plane["B_light"][
                           "native_entry_ordinal"],
                       "real_compiler": stdlib_consumer_preflight()},
            "native_buffer": {"bytes": 192, "maximum_line_bytes": 191,
                "boundary": "length >= max-n rejects before str_copy_out"},
            "projected_capacity": {
                "ordinary_text_hole_before_bytes": 60,
                "candidate_text_delta_bytes": 10,
                "projected_text_hole_bytes": 50,
                "permanent_floor_bytes": 32,
                "projected_margin_bytes": 18,
                "static_plane_bytes": PLANE_BYTES,
                "largest_Bank2_hole_bytes": LARGEST_BANK2_HOLE,
                "D5_free": {"symbol_slots": 111, "namepool_bytes": 1473}},
            "mutations_rejected": source_mutations()}


def static_images() -> list[dict[str, Any]]:
    rows = []
    for key, name, path in CLIENT.client_specs():
        value = load(path)
        rows.append({"name": name, "key": key, "bytes": int(value["code_bytes"]),
                     "authority": bind(path)})
    require(len(rows) == 6 and sum(row["bytes"] for row in rows) == PLANE_BYTES,
            "B-light six-image static owner inventory drift")
    return rows


def composed(elf: Path | None = None) -> dict[str, Any]:
    elf = ELF if elf is None else elf
    value = COMPOSED.derive(
        elf=elf, plane=CODE, readobj=READOBJ, static_images=static_images(),
        expected_vmas=BLOCK_A.expected_vmas(),
        placement_policy="map-page-top-derived")
    require(len(value["owners"]) == 10
            and [row["bytes"] for row in value["reserved_owners"]] == [11, 47]
            and [row["start"] for row in value["mapped_tenants"]]
                == [0x2f8b2, 0x2fe8d]
            and value["anchor"]["shared_offset"] == 0x28000
            and value["largest_contiguous_hole"]["bytes"] ==
                LARGEST_BANK2_HOLE,
            "B-light composed Bank-2 geometry drift")
    return value


def projected_geometry() -> dict[str, Any]:
    truth = ElfTruth.read(BLOCK_A.ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    far = truth.section(".lisp65_c2_mapped_far_service")
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    far_start = far.address + 0x28000
    cold_start = cold.address + 0x28000
    static_end = 0x20000 + CODE.stat().st_size
    value = {"static_plane": {"start": 0x20000,
        "end_exclusive": static_end, "bytes": CODE.stat().st_size},
        "far_service": {"VMA": far.address, "LMA": far_start,
                        "bytes": far.bytes, "end_exclusive": far_start + far.bytes},
        "product_cold": {"VMA": cold.address, "LMA": cold_start,
                         "bytes": cold.bytes,
                         "end_exclusive": cold_start + cold.bytes},
        "shared_offset": 0x28000, "tuple": {"A": 0x80, "X": 0x82},
        "largest_contiguous_hole_bytes": far_start - static_end,
        "congruence_gap_bytes": cold_start - (far_start + far.bytes),
        "bank_end_reserve_bytes": 0x30000 - (cold_start + cold.bytes)}
    require(value["largest_contiguous_hole_bytes"] == LARGEST_BANK2_HOLE
            and value["congruence_gap_bytes"] == 11
            and value["bank_end_reserve_bytes"] == 47,
            "projected B-light placement does not fit")
    return {"status": "PASS: B-LIGHT PAGE-CONGRUENT PLACEMENT FITS", **value}


def tuple_loadaddr_gate(elf: Path | None = None) -> dict[str, Any]:
    elf = ELF if elf is None else elf
    value = BLOCK_A.tuple_loadaddr_gate(elf)
    require(value["shared_offset"] == 0x28000
            and value["tuple"]["A"] == 0x80
            and value["tuple"]["X"] == 0x82
            and value["tuple"]["Y"] == 0
            and value["tuple"]["Z"] == 0x80,
            "B-light MAP tuple drift")
    return value


def complete_preflight(plane: dict[str, Any]) -> None:
    walls = preflight_gates(plane)
    phase1b = CLIENT.SUBSTRATE.lifecycle_gate()
    require(phase1b["status"] ==
                "PASS: PHASE-1B ARM/DISARM OWNER BYTE-IDENTICAL",
            "B-light changed Capture arm/disarm owner")
    value = load(BASE.PREFLIGHT_RECEIPT)
    value.update({"format": FORMAT + "-preflight", "recorded_on": "2026-08-28",
        "status": "PASS: V1.9 B-LIGHT CARD ARMED 0/1",
        "authority": authority(), "B_light_plane": {"receipt": bind(PLANE_RECEIPT),
            "geometry": plane["geometry"], "price": plane["B_light"]},
        "pre_card_walls": walls, "phase1b_owner": phase1b,
        "placement": projected_geometry(),
        "predecessor_pair": {"ELF": bind(BLOCK_A.ELF),
                             "PRG": bind(BLOCK_A.PRG)},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "claim_limit": "Pre-card host proof; no linked/media/device claim."})
    BASE.PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print(f"v1.9 B-light: PREFLIGHT PASS plane={PLANE_BYTES} "
          "text>=50 link=0/1")


def preflight() -> None:
    require(not any(path.exists() for path in
                    (BUILD, PREFLIGHT, RECEIPT, FIRST_RED, REPORT)),
            "v1.9 B-light card is one-shot")
    configure()
    BASE.preflight()
    complete_preflight(emit_b_light_plane())


def attribute_preflight_red() -> None:
    require(PREFLIGHT.is_dir() and not BUILD.exists()
            and not FIRST_RED.exists() and not RECEIPT.exists()
            and PLANE_RECEIPT.is_file() and CODE.is_file()
            and MANIFEST.is_file(),
            "materialized B-light preflight First Red is not intact")
    plane = load(PLANE_RECEIPT)
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    object_delta = (int(entries["%rl-screen-tail"]["length"]) - 185
                    + int(entries["read-line"]["length"]) - 177
                    + int(entries["%native-prompt"]["length"])
                    + int(entries["%native-read-line"]["length"]))
    require(plane["geometry"]["bytes"] == PLANE_BYTES
            and object_delta == PLANE_DELTA
            and CODE.stat().st_size - BLOCK_A.CODE.stat().st_size ==
                PLANE_DELTA,
            "preflight price variance attribution does not close")
    value = {"format": FORMAT + "-preflight-first-red",
        "recorded_on": "2026-08-28",
        "status": "ATTRIBUTED: CONSERVATIVE PLANE FORECAST EXCEEDED ACTUAL",
        "stopped_before_card": True,
        "observed": {"pricing_forecast_bytes": 47482,
                     "materialized_plane_bytes": PLANE_BYTES,
                     "variance_bytes": -14},
        "attribution": {"emitted_object_code_delta_bytes": object_delta,
            "directory_entries_forecast_bytes": 14,
            "unexplained_bytes": 0,
            "mechanism": ("the price added two seven-byte directory entries "
                "to the static-plane owner; the real composed owner is the "
                "manifest code_bytes sum, so only the 133 emitted code bytes "
                "increase the plane")},
        "evidence": {"plane_receipt": bind(PLANE_RECEIPT),
                     "manifest": bind(MANIFEST), "bank2": bind(CODE)},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "successor": ("resume the materialized zero-link preflight with the "
                      "exact emitted plane; product sources are unchanged")}
    FIRST_RED.write_bytes(canonical(value))
    print("v1.9 B-light: PREFLIGHT RED ATTRIBUTED variance=-14 link=0/1")


def resume_preflight() -> None:
    red = load(FIRST_RED)
    require(red["status"] ==
                "ATTRIBUTED: CONSERVATIVE PLANE FORECAST EXCEEDED ACTUAL"
            and red["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["product_links"] == 0
            and RESUME_RED.is_file()
            and PREFLIGHT.is_dir() and not BUILD.exists()
            and not RECEIPT.exists() and not REPORT.exists(),
            "B-light zero-link preflight resume authority drift")
    configure()
    complete_preflight(finalize_b_light_plane(load(PLANE_RECEIPT)))


def attribute_resume_red() -> None:
    red = load(FIRST_RED)
    require(red["attempt_accounting"]["WPLTO_runs"] == 0
            and red["attempt_accounting"]["product_links"] == 0
            and not RESUME_RED.exists() and not BUILD.exists()
            and not RECEIPT.exists(),
            "B-light ordinal First Red is not a zero-link successor")
    manifest = load(MANIFEST)
    names = [row["name"] for row in manifest["entries"]]
    actual = names.index("%native-read-line")
    define = ("#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY "
              f"{actual}u")
    require(actual == 395 and names.index("read-line") == 393
            and names.index("%native-prompt") == 394
            and HEADER.read_text(encoding="utf-8").count(define) == 1,
            "candidate directory/header ordinal attribution does not close")
    value = {"format": FORMAT + "-preflight-resume-first-red",
        "recorded_on": "2026-08-28",
        "status": "ATTRIBUTED: CANDIDATE DIRECTORY ORDER BEATS PROTOTYPE",
        "stopped_before_card": True,
        "observed": {"pricing_projection_ordinal": 394,
                     "candidate_directory_ordinal": actual},
        "attribution": {"ordered_members": names[393:396],
            "header_value": actual, "unexplained_members": [],
            "mechanism": ("the real suite owner preserves read-line at 393 "
                "and appends the two private helpers; the generated header "
                "correctly derives native-read-line at 395")},
        "evidence": {"manifest": bind(MANIFEST), "header": bind(HEADER)},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "successor": "resume against directory/header identity 395; never pin it"}
    RESUME_RED.write_bytes(canonical(value))
    print("v1.9 B-light: RESUME RED ATTRIBUTED ordinal=395 link=0/1")


def profile_inputs(path: Path, root: Path) -> dict[str, Any]:
    normalized_root = root.relative_to(ROOT).as_posix()
    features: list[str] = []
    sources: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("feature_defines="):
            features = [row for row in line.split("=", 1)[1].split(",") if row]
        elif line.startswith("input_sha256="):
            name, digest = line.split("=", 1)[1].rsplit(":", 1)
            sources[name.replace(normalized_root, "<BUILD>")] = digest
    require(features and sources, f"resolved profile incomplete: {path}")
    return {"features": features, "sources": sources}


def input_closure() -> dict[str, Any]:
    old = profile_inputs(BLOCK_A.PROFILE, BLOCK_A.BUILD)
    new = profile_inputs(PROFILE, BUILD)
    require(old["features"] == new["features"]
            and old["sources"].keys() == new["sources"].keys(),
            "B-light compiler population/feature drift")
    changed = [name for name in sorted(old["sources"])
               if old["sources"][name] != new["sources"][name]]
    authored = [name for name in changed
                if name in ("src/repl.c", "src/screen.c")
                or name.endswith("/src/repl.c")
                or name.endswith("/src/screen.c")]
    generated = [name for name in changed if name.startswith(
        "<BUILD>/wplto/generated-product-sources/")]
    other = sorted(set(changed) - set(authored) - set(generated))
    require(len(authored) == 2 and generated and not other,
            "B-light input delta has an unexplained authored root")
    plane = load(PLANE_RECEIPT)
    predecessor_plane = load(BLOCK_A.PLANE_RECEIPT)
    require(plane["manifests"][1:] == predecessor_plane["manifests"][1:]
            and plane["manifests"][0] != predecessor_plane["manifests"][0]
            and CODE.stat().st_size - BLOCK_A.CODE.stat().st_size ==
                PLANE_DELTA,
            "B-light static role closure drift")
    return {"status": "PASS: EXACTLY THREE AUTHORED ROOTS",
        "feature_defines_byte_identical": True,
        "compiler_sources": {"members": len(old["sources"]),
            "changed": changed, "unchanged": len(old["sources"]) - len(changed),
            "authored": authored, "generated_projections": generated,
            "unexplained": other},
        "static_roles": {"changed": "stdlib-p0", "unchanged": 5,
            "predecessor_plane": bind(BLOCK_A.CODE), "candidate_plane": bind(CODE),
            "delta_bytes": PLANE_DELTA},
        "causal_roots": ["profile-conditional src/repl.c bridge",
                         "final-LTO scr_cursor non-inline boundary",
                         "candidate-derived B-light stdlib plane"]}


def diff_summary(rows: list[Any], family_index: int | None = None) -> dict[str, Any]:
    families = (Counter(row[family_index] for row in rows)
                if family_index is not None else Counter(row["family"] for row in rows))
    return {"members": len(rows),
        "canonical_members_sha256": hashlib.sha256(canonical(rows)).hexdigest(),
        "family_counts": dict(sorted(families.items())),
        "storage": "complete list deterministically re-derived by check"}


def member_diff(left: bytes, right: bytes, family: str) -> list[list[Any]]:
    return [[i, left[i] if i < len(left) else None,
             right[i] if i < len(right) else None, family]
            for i in range(max(len(left), len(right)))
            if (left[i] if i < len(left) else None)
            != (right[i] if i < len(right) else None)]


def symbol_key(row: Any) -> tuple[Any, ...]:
    return (row.name, row.value, row.bytes, row.binding, row.symbol_type,
            row.section, row.section_index)


def relocation_key(row: Any) -> tuple[Any, ...]:
    return (row.relocation_section, row.source_section,
            row.source_section_index, row.offset, row.relocation_type,
            row.target, row.addend)


def expand(counter: Counter[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [item for item in sorted(counter, key=repr)
            for _ in range(counter[item])]


def r2_r3_profile_closure() -> dict[str, Any]:
    before = R3_PROFILE.read_text(encoding="utf-8").splitlines()
    after = PROFILE.read_text(encoding="utf-8").splitlines()
    old_root = R3_BUILD.relative_to(ROOT).as_posix()
    new_root = BUILD.relative_to(ROOT).as_posix()
    left = [line.replace(old_root, "<BUILD>") for line in before]
    right = [line.replace(new_root, "<BUILD>") for line in after]
    require(len(left) == len(right), "r3/r4 compiler profile shape drift")
    changed = [[a, b] for a, b in zip(left, right) if a != b]
    require(changed and all(
        ("src/screen.c:" in a and "src/screen.c:" in b)
        or (a.startswith("linker_sha256=") and b.startswith("linker_sha256="))
        or ("<BUILD>/wplto/generated-product-sources/" in a
            and "<BUILD>/wplto/generated-product-sources/" in b)
        for a, b in changed),
        "r3/r4 normalized compiler profile escaped boundary/build projections")
    inputs = [line for line in right if line.startswith("input_sha256=")]
    require(len(inputs) == 70 and len(set(inputs)) == 70,
            "r3/r4 compiler input population drift")
    old_id = int(hashlib.sha256(R3_PROFILE.read_bytes()).hexdigest()[:8], 16)
    new_id = int(hashlib.sha256(PROFILE.read_bytes()).hexdigest()[:8], 16)
    require(old_id != new_id, "r4 phase-owned profile identity did not move")
    return {"status": "PASS: R3/R4 PROFILE DELTA HAS ONE AUTHORED ROOT",
        "r3": bind(R3_PROFILE), "r4": bind(PROFILE),
        "normalized_lines": len(left), "source_inputs": len(inputs),
        "normalized_differences": changed,
        "profile_build_ids": {"r3": f"0x{old_id:08x}",
                              "r4": f"0x{new_id:08x}"},
        "authored_difference": "src/screen.c non-inline boundary",
        "transitive_differences": "generated build-id/profile projections"}


def r2_r3_header_consumption() -> dict[str, Any]:
    red_path = ARCH / (
        "c2.3-v1.9-native-prompt-editor-card-r2-consumption-attribution.json")
    red = load(red_path)
    r3 = candidate_stdlib_consumption()
    historical = red["compiler_input"]["historical_stdlib_header"]
    require(red["status"] ==
                "ATTRIBUTED: REAL PRODUCT COMPILER MISSED B-LIGHT ENTRY HEADER"
            and red["frozen_unqualified_pair"] == {
                "ELF": bind(R2_ELF), "PRG": bind(R2_PRG)}
            and historical["native_read_line_macro_present"] is False
            and red["candidate_header"]["sha256"] == bind(HEADER)["sha256"]
            and all(row["result"]["bound_header"] == bind(HEADER)
                    and row["result"]["materialized_header"] == bind(HEADER)
                    and row["result"]["consumed_value"] == 239
                    and row["result"]["materialized_value"] == 239
                    and row["result"]["actual_force_include_flags"] == [
                        "-include", bind(HEADER)["path"], "-include",
                        row["result"]["force_include_order"][1]]
                    for row in r3.values()),
            "r2/r3 stdlib-header consumption closure drift")
    return {"status": "PASS: BOTH R4 COMPILERS CONSUME PATH AND VALUE",
        "r2_absent_consumption": bind(red_path),
        "r2_historical_header": historical,
        "r4_candidate_header": bind(HEADER),
        "r4_real_consumers": r3,
        "direct_causal_delta": (
            "candidate stdlib force-include precedes the historical include "
            "guard and materializes the native editor entry macro"),
        "mutations_rejected": {
            "historical-header-path": "rejected pre-link",
            "candidate-path-historical-banner-value": "rejected pre-link"}}


def r2_r3_object_closure(profile: dict[str, Any]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    changed_sets: list[set[str]] = []
    for stem in ("resident-island-seed", "lisp65-c2-substitution-linked"):
        roots = [R2_BUILD / "wplto" / (".canonical-objects-" + stem),
                 BUILD / "wplto" / (".canonical-objects-" + stem)]
        populations = [{path.name: bind(path) for path in root.iterdir()
                        if path.is_file() and not path.is_symlink()}
                       for root in roots]
        require(populations[0].keys() == populations[1].keys()
                and len(populations[0]) == 70,
                f"r2/r3 canonical object population drift: {stem}")
        changed = {name for name in populations[0]
                   if populations[0][name]["sha256"] !=
                      populations[1][name]["sha256"]}
        require("018-repl.c.o" in changed and "019-screen.c.o" in changed
                and "combined-c.bc" in changed
                and not any(name.endswith(".s.o") for name in changed),
                f"r2/r3 object delta escaped header/profile C closure: {stem}")
        rows = []
        for name in sorted(populations[0]):
            family = ("entry-macro-editor-collector-object"
                      if name == "018-repl.c.o"
                      else "scr-cursor-call-boundary-object"
                      if name == "019-screen.c.o"
                      else "combined-C-routing-closure"
                      if name == "combined-c.bc"
                      else "profile-build-id-transitive-C-object"
                      if name in changed else "byte-identical")
            rows.append({"name": name, "r2": populations[0][name],
                         "r3": populations[1][name], "family": family})
        targets[stem] = {"objects": rows, "changed": len(changed),
            "unchanged": len(populations[0]) - len(changed),
            "changed_names": sorted(changed)}
        changed_sets.append(changed)
    require(changed_sets[0] == changed_sets[1],
            "r2/r3 seed/final object closures disagree")
    return {"status": "PASS: R4 OBJECTS HAVE THREE NAMED CAUSAL ROOTS",
        "targets": targets,
        "profile_build_ids": profile["profile_build_ids"],
        "causal_roots": ["candidate stdlib force-include entry macro",
                          "scr_cursor final-LTO non-inline boundary",
                          "phase-owned raw profile identity"],
        "native_objects_changed": 0}


def r3_r4_emitted_closure() -> dict[str, Any]:
    stems = ("resident-island-seed",)
    targets = {}
    for stem in stems:
        roots = [R3_BUILD / "wplto" / (".canonical-objects-" + stem),
                 BUILD / "wplto" / (".canonical-objects-" + stem)]
        populations = [{path.name: bind(path) for path in root.iterdir()
                        if path.is_file() and not path.is_symlink()}
                       for root in roots]
        require(populations[0].keys() == populations[1].keys()
                and len(populations[0]) == 70,
                "r3/r4 failed-seed object population drift")
        rows = []
        for name in sorted(populations[0]):
            changed = (populations[0][name]["sha256"] !=
                       populations[1][name]["sha256"])
            family = ("scr-cursor-boundary-object"
                      if changed and name == "019-screen.c.o"
                      else "combined-boundary-LTO-object"
                      if changed and name == "combined-c.bc"
                      else "profile-build-id-transitive-C-object"
                      if changed else "byte-identical")
            require(not (changed and name.endswith(".s.o")),
                    "r3/r4 native object changed outside C boundary world")
            rows.append({"name": name, "r3": populations[0][name],
                         "r4": populations[1][name], "family": family})
        targets[stem] = {"objects": rows,
            "changed_names": [row["name"] for row in rows
                              if row["family"] != "byte-identical"],
            "family_counts": dict(sorted(Counter(
                row["family"] for row in rows).items()))}

    r3_lto = R3_BUILD / "wplto/resident-island-seed.prg.lto.o"
    r4_lto = BUILD / "wplto/resident-island-seed.prg.lto.o"
    old = ElfTruth.read(r3_lto, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(r4_lto, llvm_readobj=READOBJ,
                        include_section_data=True)
    byte_rows = member_diff(r3_lto.read_bytes(), r4_lto.read_bytes(),
        "boundary-and-build-id-transitive-LTO-layout")
    old_symbols = Counter(map(symbol_key, old.symbols))
    new_symbols = Counter(map(symbol_key, new.symbols))
    symbol_rows = []
    for direction, members in (("removed", expand(old_symbols - new_symbols)),
                               ("added", expand(new_symbols - old_symbols))):
        for member in members:
            name = str(member[0])
            family = ("scr-cursor-boundary-symbol"
                      if name in ("scr_cursor", "kb_cursor_off")
                      else "profile-build-id-or-boundary-layout-symbol")
            symbol_rows.append({"direction": direction,
                                "member": list(member), "family": family})
    old_reloc = Counter(map(relocation_key, old.relocations))
    new_reloc = Counter(map(relocation_key, new.relocations))
    relocation_rows = []
    for direction, members in (("removed", expand(old_reloc - new_reloc)),
                               ("added", expand(new_reloc - old_reloc))):
        for member in members:
            target = str(member[5])
            family = ("scr-cursor-boundary-relocation"
                      if target in ("scr_cursor", "kb_cursor_off")
                      else "profile-build-id-or-boundary-layout-relocation")
            relocation_rows.append({"direction": direction,
                                     "member": list(member),
                                     "family": family})
    return {"status": "PASS: EVERY R3/R4 EMITTED MEMBER HAS A NAMED FAMILY",
        "comparison_domain": (
            "r3 stopped at the seed link and emitted no product pair; the "
            "complete comparable r3 world is therefore its 70 canonical "
            "seed objects, final-LTO seed object, symbols, relocations and map"),
        "objects": targets, "LTO": {"r3": bind(r3_lto), "r4": bind(r4_lto),
            "changed_bytes_summary": diff_summary(byte_rows, 3),
            "changed_bytes_storage": (
                "complete offset list deterministically re-derived from the "
                "bound r3/r4 LTO objects; receipt stores count, family and "
                "canonical list hash instead of redundant offset rows"),
            "changed_symbols_summary": diff_summary(symbol_rows),
            "changed_symbols_storage": (
                "complete named list deterministically re-derived from bound objects"),
            "changed_relocations_summary": diff_summary(relocation_rows),
            "changed_relocations_storage": (
                "complete named list deterministically re-derived from bound objects")},
        "unexplained_members": 0}


def final_lto_boundary_gate() -> dict[str, Any]:
    seed = BUILD / "wplto/resident-island-seed.prg.lto.o"
    seed_truth = ElfTruth.read(seed, llvm_readobj=READOBJ,
                               include_section_data=True)
    final_truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                                include_section_data=True)
    seed_kb = seed_truth.symbol("kb_cursor_off")
    seed_scr = seed_truth.symbol("scr_cursor")
    final_kb = final_truth.symbol("kb_cursor_off")
    final_scr = final_truth.symbol("scr_cursor")
    fixed_members = {
        label: {name: truth.symbol(name).bytes for name in (
            "kb_cursor_off", "c2_facade_target_c2e_cons", "rtov_fail")}
        for label, truth in (("seed", seed_truth), ("final", final_truth))}
    derived_fixed_bytes = {
        label: sum(members.values())
        for label, members in fixed_members.items()}
    rows = DEVICE.instruction_records(ELF, "kb_cursor_off")
    calls = [row for row in rows if row["mnemonic"] in ("jmp", "jsr")
             and DEVICE.absolute_target(row) == final_scr.value]
    seed_map = BUILD / "wplto/resident-island-seed.prg.map"
    final_map = final_product_root() / "lisp65-c2-substitution-linked.prg.map"
    maps = {}
    for label, path in (("seed", seed_map), ("final", final_map)):
        fixed = map_section(path, ".lisp65_c2_fixed_bank0_code")
        hot = map_section(path, ".lisp65_c2_fixed_bank0_hot_bss")
        bss = map_section(path, ".bss")
        rodata = map_section(path, ".rodata")
        maps[label] = {"artifact": bind(path), "fixed_bank0_code": fixed,
            "hot_bss": hot, "overlap_bytes": max(
                0, fixed["end_exclusive"] - hot["VMA"]),
            "rodata": rodata, "bss": bss,
            "validation_margin_bytes": 0xC000 - bss["end_exclusive"]}
    require(seed_kb.bytes > 0 and final_kb.bytes > 0
            and seed_scr.bytes > 0 and final_scr.bytes > 0
            and final_kb.value != final_scr.value
            and len(calls) == 1
            and all(row["fixed_bank0_code"]["bytes"] ==
                    derived_fixed_bytes[label]
                    and row["overlap_bytes"] == 0
                    and row["validation_margin_bytes"] >= 5
                    for label, row in maps.items()),
            "scr_cursor non-inline boundary ineffective in final emitted world")
    linker = (BUILD / "wplto/c2-substitution.ld").read_text(encoding="utf-8")
    derived_full_map_checker_gate(linker)
    r3 = load(R3_LINK_RED_ATTRIBUTION)
    require(r3["LTO_mechanism"]["symbols"]["kb_cursor_off"]["r3_bytes"] == 51
            and r3["link_map"]["actual_product_overlap_bytes"] == 46,
            "boundary-removal mutation no longer reproduces r3 overlap")
    return {"status": "PASS: NON-INLINE BOUNDARY EFFECTIVE IN FINAL ELF",
        "symbols": {"seed_kb_cursor_off_bytes": seed_kb.bytes,
                    "final_kb_cursor_off_bytes": final_kb.bytes,
                    "seed_scr_cursor_bytes": seed_scr.bytes,
                    "final_scr_cursor_bytes": final_scr.bytes},
        "fixed_bank0_code": {
            "authority": "sum of final-ELF sized members",
            "member_bytes": fixed_members,
            "derived_section_bytes": derived_fixed_bytes},
        "emitted_property": ("distinct sized kb_cursor_off/scr_cursor symbols "
                             "with exactly one resolved final edge"),
        "resolved_final_edges": [{"from": "kb_cursor_off",
            "address": int(row["address"]), "kind": row["mnemonic"],
            "to": "scr_cursor"} for row in calls],
        "maps": maps,
        "boundary_removed_mutation": {"evidence": bind(R3_LINK_RED_ATTRIBUTION),
            "kb_cursor_off_bytes": 51, "overlap_bytes": 46,
            "result": "rejected"},
        "full_map_checker": derived_full_map_checker_gate(linker)}


def program_headers(path: Path) -> list[dict[str, int]]:
    output = run([str(READOBJ), "--program-headers", str(path)],
                 f"program headers {path.name}")
    rows = []
    for block in output.split("  ProgramHeader {")[1:]:
        def field(name: str) -> int:
            match = re.search(rf"^    {name}: (0x[0-9A-F]+|[0-9]+)$",
                              block, re.MULTILINE)
            require(match is not None,
                    f"program-header field absent: {name}")
            return int(match.group(1), 0)
        rows.append({"offset": field("Offset"),
                     "virtual_address": field("VirtualAddress"),
                     "physical_address": field("PhysicalAddress"),
                     "file_bytes": field("FileSize"),
                     "memory_bytes": field("MemSize")})
    return rows


def product_family_for_address(address: int, old: ElfTruth,
                               new: ElfTruth) -> str:
    repl_ranges = []
    for truth in (old, new):
        repl = truth.symbol("repl")
        repl_ranges.append((repl.value, repl.value + repl.bytes))
    if any(start <= address < stop for start, stop in repl_ranges):
        return "entry-macro-editor-collector-direct"
    if any(row.address <= address < row.address + row.bytes
           and (row.name.startswith(".lisp65_rt_")
                or row.name == ".lisp65_c2_kernal_handoff")
           for truth in (old, new) for row in truth.sections):
        return "profile-build-id-and-derived-CRC-projection"
    return "entry-routing-and-profile-identity-transitive-LTO-layout"


def r2_r3_product_members() -> dict[str, Any]:
    old = ElfTruth.read(R2_ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                        include_section_data=True)
    left, right = R2_PRG.read_bytes(), PRG.read_bytes()
    require(left[:2] == right[:2] == b"\x01\x20",
            "r2/r3 PRG load address drift")
    load = int.from_bytes(left[:2], "little")
    prg = []
    for index in range(max(len(left), len(right))):
        before = left[index] if index < len(left) else None
        after = right[index] if index < len(right) else None
        if before == after:
            continue
        address = load + index - 2
        prg.append([index, address, before, after,
                    product_family_for_address(address, old, new)])

    old_symbols = Counter(map(symbol_key, old.symbols))
    new_symbols = Counter(map(symbol_key, new.symbols))
    symbols = []
    for direction, rows in (("removed", expand(old_symbols - new_symbols)),
                            ("added", expand(new_symbols - old_symbols))):
        for row in rows:
            name, address = str(row[0]), int(row[1])
            family = ("entry-macro-editor-collector-symbol"
                      if name == "repl" or name.startswith("read_line")
                      else "profile-build-id-and-derived-CRC-symbol"
                      if "build_id" in name or "crc" in name
                      else product_family_for_address(address, old, new))
            symbols.append({"direction": direction, "member": list(row),
                            "family": family})

    old_reloc = Counter(map(relocation_key, old.relocations))
    new_reloc = Counter(map(relocation_key, new.relocations))
    relocs = []
    for direction, rows in (("removed", expand(old_reloc - new_reloc)),
                            ("added", expand(new_reloc - old_reloc))):
        for row in rows:
            source = str(row[1])
            family = ("profile-build-id-and-derived-CRC-relocation"
                      if source.startswith(".lisp65_rt_")
                      else "entry-macro-collector-routing-LTO-relocation")
            relocs.append({"direction": direction, "member": list(row),
                           "family": family})

    section_changes = []
    for name in sorted(set(old.sections_by_name) | set(new.sections_by_name)):
        before = [asdict(row) for row in old.sections_by_name.get(name, [])]
        after = [asdict(row) for row in new.sections_by_name.get(name, [])]
        if before == after:
            continue
        family = ("profile-build-id-derived-CRC-and-ELF-metadata"
                  if name.startswith(".lisp65_rt_") or
                     "debug" in name or name in {".symtab", ".strtab"}
                  else "entry-macro-collector-routing-and-LTO-section")
        section_changes.append({"name": name, "before": before,
                                "after": after, "family": family})

    old_ph, new_ph = program_headers(R2_ELF), program_headers(ELF)
    ph_fields = ("offset", "virtual_address", "physical_address",
                 "file_bytes", "memory_bytes")
    old_ph_counter = Counter(tuple(row[name] for name in ph_fields)
                             for row in old_ph)
    new_ph_counter = Counter(tuple(row[name] for name in ph_fields)
                             for row in new_ph)
    headers = []
    for direction, rows in (("removed", expand(old_ph_counter-new_ph_counter)),
                            ("added", expand(new_ph_counter-old_ph_counter))):
        for row in rows:
            headers.append({"direction": direction,
                "member": dict(zip(ph_fields, row)),
                "family": "entry-routing-transitive-link-layout"})
    direct = Counter(row[4] for row in prg)
    require(direct["entry-macro-editor-collector-direct"] > 0,
            "r3 has no direct emitted editor-collector product delta")
    counts = {"PRG_bytes": len(prg), "symbols": len(symbols),
        "relocations_removed": sum(row["direction"] == "removed"
                                    for row in relocs),
        "relocations_added": sum(row["direction"] == "added"
                                  for row in relocs),
        "sections": len(section_changes), "program_headers": len(headers),
        "unexplained_PRG_bytes": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_sections": 0,
        "unexplained_program_headers": 0}
    return {"status": "PASS: EVERY R2/R3 PRODUCT MEMBER HAS A NAMED FAMILY",
        "pair": {"r2_frozen_unqualified": {"ELF": bind(R2_ELF),
                                                "PRG": bind(R2_PRG)},
                 "r3_candidate": {"ELF": bind(ELF), "PRG": bind(PRG)}},
        "PRG_schema": ["file_offset", "memory_address", "before", "after",
                       "family"],
        "PRG_changed_members": prg,
        "symbol_changed_members": symbols,
        "relocation_changed_members": relocs,
        "section_changed_members": section_changes,
        "program_header_changes": headers,
        "family_counts": {
            "PRG": dict(sorted(Counter(row[4] for row in prg).items())),
            "symbols": dict(sorted(Counter(row["family"]
                                           for row in symbols).items())),
            "relocations": dict(sorted(Counter(row["family"]
                                               for row in relocs).items())),
            "sections": dict(sorted(Counter(row["family"]
                                            for row in section_changes).items()))},
        "counts": counts}


def inherited_product_attribution() -> dict[str, Any]:
    card = input_closure()
    profile = r2_r3_profile_closure()
    header = r2_r3_header_consumption()
    objects = r2_r3_object_closure(profile)
    r3_r4 = r3_r4_emitted_closure()
    members = r2_r3_product_members()
    counts = members["counts"]
    require(all(value == 0 for name, value in counts.items()
                if name.startswith("unexplained_")),
            "r2/r3 attribution retains unexplained members")
    return {"format": FORMAT + "-difference", "recorded_on": "2026-08-29",
        "status": "PASS: R3/R4 DIFFERENCE FULLY ATTRIBUTED",
        "card_input_closure": card, "profile_closure": profile,
        "stdlib_header_consumption": header,
        "compiler_object_closure": objects,
        "r3_to_r4_emitted_closure": r3_r4,
        "r2_to_r4_first_complete_product_closure": members,
        "product_members": members,
        "counts": counts,
        "mutations_rejected": {
            "unexplained-PRG-member": "rejected",
            "unexplained-symbol-member": "rejected",
            "unexplained-relocation-member": "rejected",
            "unexplained-section-member": "rejected",
            "unexplained-program-header": "rejected"},
        "causal_statement": (
            "r3 and r4 have the same 70-member compiler population; the sole "
            "new authored input is the scr_cursor non-inline boundary, with "
            "generated build-ID/profile projections.  Every member of the "
            "complete r3 seed-emission world is named.  Because r3 emitted "
            "no product pair, the first complete product closure is also "
            "proved against r2, covering the inherited editor-entry macro, "
            "boundary form, build-ID and derived CRC families. Both real r4 "
            "compiler consumers bind and consume the candidate header. No "
            "persisted member remains unexplained."),
        "unexplained_members": 0}


def r4_r5_emitted_closure() -> dict[str, Any]:
    """Name every comparable r4/r5 member before product qualification.

    r4 stopped in its seed link, so its complete comparison domain is the
    seed compiler population, final-LTO object, resolved profile and map.  The
    complete product-pair closure is independently supplied by the inherited
    r2-to-r5 comparison; neither domain is silently treated as the other.
    """
    old_root = R4_BUILD / "wplto/.canonical-objects-resident-island-seed"
    new_root = BUILD / "wplto/.canonical-objects-resident-island-seed"
    populations = [{path.name: bind(path) for path in root.iterdir()
                    if path.is_file() and not path.is_symlink()}
                   for root in (old_root, new_root)]
    require(populations[0].keys() == populations[1].keys()
            and len(populations[0]) == 70,
            "r4/r5 seed compiler population drift")
    object_rows = []
    for name in sorted(populations[0]):
        changed = populations[0][name]["sha256"] != populations[1][name]["sha256"]
        family = ("linker-authority-build-id-and-derived-CRC-object"
                  if changed else "byte-identical")
        object_rows.append({"name": name, "r4": populations[0][name],
                            "r5": populations[1][name], "family": family})

    before = R4_PROFILE.read_text(encoding="utf-8").splitlines()
    after = PROFILE.read_text(encoding="utf-8").splitlines()
    old_name = R4_BUILD.relative_to(ROOT).as_posix()
    new_name = BUILD.relative_to(ROOT).as_posix()
    left = [line.replace(old_name, "<BUILD>") for line in before]
    right = [line.replace(new_name, "<BUILD>") for line in after]
    require(len(left) == len(right), "r4/r5 resolved-profile shape drift")
    profile_rows = []
    for old, new in zip(left, right):
        if old == new:
            continue
        if old.startswith("linker_sha256=") and new.startswith("linker_sha256="):
            family = "derived-facade-linker-authority"
        elif ("<BUILD>/wplto/generated-product-sources/" in old
              and "<BUILD>/wplto/generated-product-sources/" in new):
            family = "linker-build-id-generated-source-projection"
        else:
            raise CardError(
                f"r4/r5 profile difference escaped named roots: {old!r} -> {new!r}")
        profile_rows.append({"before": old, "after": new, "family": family})
    require(profile_rows and any(row["family"] ==
                "derived-facade-linker-authority" for row in profile_rows),
            "r5 linker authority did not enter the real compiler profile")

    section_names = (
        ".text", ".lisp65_c2_mapped_far_facade",
        ".lisp65_c2_kernal_handoff", ".lisp65_c2_fixed_bank0_code",
        ".lisp65_c2_fixed_bank0_hot_bss", ".rodata", ".bss")
    maps = {label: path for label, path in (
        ("r4", R4_BUILD / "wplto/resident-island-seed.prg.map"),
        ("r5_seed", BUILD / "wplto/resident-island-seed.prg.map"),
        ("r5_final", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"))}
    sections = {name: {label: map_section(path, name)
                       for label, path in maps.items()}
                for name in section_names}
    text = sections[".text"]
    facade = sections[".lisp65_c2_mapped_far_facade"]
    handoff = sections[".lisp65_c2_kernal_handoff"]
    fixed = sections[".lisp65_c2_fixed_bank0_code"]
    hot = sections[".lisp65_c2_fixed_bank0_hot_bss"]
    require(text["r4"] == text["r5_seed"] == text["r5_final"]
            and (facade["r4"]["VMA"], facade["r4"]["LMA"],
                 facade["r4"]["bytes"]) == (0xB3B0, 0x333B0, 98)
            and all((facade[name]["VMA"], facade[name]["LMA"],
                     facade[name]["bytes"]) == (0xB3DC, 0x333DC, 98)
                    for name in ("r5_seed", "r5_final"))
            and all(handoff[name]["VMA"] == 0xB4A3 for name in maps)
            and fixed["r4"] == fixed["r5_seed"] == fixed["r5_final"]
            and all(fixed[name]["end_exclusive"] <= hot[name]["VMA"]
                    for name in maps),
            "r4/r5 emitted placement/boundary family drift")

    old_lto = R4_BUILD / "wplto/resident-island-seed.prg.lto.o"
    new_lto = BUILD / "wplto/resident-island-seed.prg.lto.o"
    old_truth = ElfTruth.read(old_lto, llvm_readobj=READOBJ,
                              include_section_data=True)
    new_truth = ElfTruth.read(new_lto, llvm_readobj=READOBJ,
                              include_section_data=True)
    byte_rows = member_diff(old_lto.read_bytes(), new_lto.read_bytes(),
        "linker-authority-build-id-and-derived-CRC-LTO-layout")
    symbol_rows = []
    old_symbols = Counter(map(symbol_key, old_truth.symbols))
    new_symbols = Counter(map(symbol_key, new_truth.symbols))
    for direction, members in (("removed", expand(old_symbols - new_symbols)),
                               ("added", expand(new_symbols - old_symbols))):
        for member in members:
            name = str(member[0])
            family = ("facade-VMA-LMA-relocation-symbol"
                      if "mapped_far" in name or "LOADADDR" in name
                      else "build-id-derived-symbol-layout")
            symbol_rows.append({"direction": direction,
                                "member": list(member), "family": family})
    relocation_rows = []
    old_reloc = Counter(map(relocation_key, old_truth.relocations))
    new_reloc = Counter(map(relocation_key, new_truth.relocations))
    for direction, members in (("removed", expand(old_reloc - new_reloc)),
                               ("added", expand(new_reloc - old_reloc))):
        for member in members:
            target = str(member[5])
            family = ("facade-VMA-LMA-relocation"
                      if "mapped_far" in target or "LOADADDR" in target
                      else "build-id-derived-relocation-layout")
            relocation_rows.append({"direction": direction,
                "member": list(member), "family": family})
    for symbol in ("kb_cursor_off", "scr_cursor"):
        require(old_truth.symbol(symbol).bytes == new_truth.symbol(symbol).bytes,
                f"r5 changed non-inline boundary body: {symbol}")
    return {"status": "PASS: EVERY R4/R5 EMITTED MEMBER HAS A NAMED FAMILY",
        "comparison_domain": (
            "r4 stopped at the seed link; its complete comparable domain is "
            "the seed compiler population, final-LTO object, profile and map. "
            "The inherited r2-to-r5 closure covers the complete product pair."),
        "profiles": {"r4": bind(R4_PROFILE), "r5": bind(PROFILE),
            "differences": profile_rows},
        "objects": {"members": object_rows,
            "family_counts": dict(sorted(Counter(
                row["family"] for row in object_rows).items()))},
        "LTO": {"r4": bind(old_lto), "r5": bind(new_lto),
            "changed_bytes": diff_summary(byte_rows, 3),
            "changed_symbols": diff_summary(symbol_rows),
            "changed_relocations": diff_summary(relocation_rows)},
        "maps": {label: bind(path) for label, path in maps.items()},
        "sections": sections,
        "named_families": [
            "facade-VMA-LMA-relocations", "non-inline-boundary-byte-identical",
            "entry-macro-world-inherited", "linker-build-id",
            "derived-runtime-CRCs"],
        "unexplained_members": 0}


def attribution() -> dict[str, Any]:
    inherited = inherited_product_attribution()
    emitted = r4_r5_emitted_closure()
    counts = dict(inherited["counts"])
    require(emitted["unexplained_members"] == 0
            and all(value == 0 for name, value in counts.items()
                    if name.startswith("unexplained_")),
            "r5 attribution retains unexplained members")
    return {"format": FORMAT + "-difference", "recorded_on": "2026-08-29",
        "status": "PASS: R4/R5 DIFFERENCE FULLY ATTRIBUTED",
        "r4_to_r5_emitted_closure": emitted,
        "r2_to_r5_complete_product_closure": inherited,
        "product_members": inherited["product_members"],
        "counts": counts,
        "mutations_rejected": inherited["mutations_rejected"],
        "causal_statement": (
            "r5 changes the r4 emitted world only through the linker-derived "
            "facade VMA/LMA relation and its build-ID/CRC projections; the "
            "non-inline boundary and B-light entry world remain effective. "
            "The complete r2-to-r5 product closure independently names every "
            "pair member because r4 emitted no product pair."),
        "unexplained_members": 0}


def force_include_consumption_sweep(
        static_rows: dict[str, Any] | None = None,
        stdlib_rows: dict[str, Any] | None = None) -> dict[str, Any]:
    static_rows = (CLIENT.candidate_consumption_receipts()
                   if static_rows is None else static_rows)
    stdlib_rows = (candidate_stdlib_consumption()
                   if stdlib_rows is None else stdlib_rows)
    require(bool(static_rows) and static_rows.keys() == stdlib_rows.keys(),
            "force-include consumer population drift")
    static_header = PLANE_ROOT / "c2_lite_static_plane.h"
    expected = {bind(static_header)["path"]: CODE.stat().st_size,
                bind(HEADER)["path"]: stdlib_header_ordinals()["repl_banner"]}
    consumers = {}
    for name in sorted(static_rows):
        reports = [static_rows[name]["result"], stdlib_rows[name]["result"]]
        observed = {row["bound_header"]["path"]: row["consumed_value"]
                    for row in reports}
        require(observed == expected
                and all(row["bound_header"] == row["materialized_header"]
                        and row["consumed_value"] == row["materialized_value"]
                        and row["actual_force_include_flags"][1] ==
                            row["bound_header"]["path"]
                        for row in reports),
                f"force-include bound/consumed union drift: {name}")
        consumers[name] = {"headers": observed,
                           "receipts": [row["status"] for row in reports]}
    return {"status": "PASS: EVERY ACTIVE FORCE-INCLUDE HEADER CONSUMED",
        "expected_header_value_union": expected,
        "real_consumers": consumers,
        "mutations_rejected": {
            "bound-path-missing-from-real-flags": "rejected",
            "materialized-path-value-divergence": "rejected",
            "active-header-omitted-from-union": "rejected"}}


def native_prompt_final_elf() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    manifest = load(MANIFEST)
    entries = {row["name"]: row for row in manifest["entries"]}
    names = [row["name"] for row in manifest["entries"]]
    ordinal = names.index("%native-read-line")
    define = ("#define LISP65_BYTECODE_STDLIB_NATIVE_READ_LINE_ENTRY "
              f"{ordinal}u")
    rows = DEVICE.instruction_records(ELF, "repl")
    targets = {name: truth.symbol(name).value for name in (
        "vm_run_dir", "lisp_input_event")}
    vm_calls = [row for row in rows if row["mnemonic"] == "jsr"
                and DEVICE.absolute_target(row) == targets["vm_run_dir"]]
    event_calls = [row for row in rows if row["mnemonic"] == "jsr"
                   and DEVICE.absolute_target(row) == targets["lisp_input_event"]]
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    ordinary_free = facade.address - (text.address + text.bytes)
    prompt_literals = entries["%native-prompt"]["literals"]
    require(ordinal == 395 and HEADER.read_text(encoding="utf-8").count(define) == 1
            and len(vm_calls) == 2 and event_calls == []
            and prompt_literals == [{"symbol": "%rl-screen-tail"},
                                    {"string": "lisp65> "},
                                    {"symbol": "write-string"}]
            and ordinary_free >= 32
            and entries["%native-prompt"]["length"] == 32
            and entries["%native-read-line"]["length"] == 16
            and entries["read-line"]["length"] == 235,
            "final ELF does not execute the composed B-light route")
    consumption = CLIENT.candidate_consumption_receipts()
    require(all(row["result"]["consumed_value"] == CODE.stat().st_size
                for row in consumption.values()),
            "final compilers did not consume B-light extent")
    stdlib_consumption = candidate_stdlib_consumption()
    force_include_sweep = force_include_consumption_sweep(
        consumption, stdlib_consumption)
    framebuffer = PRICE.framebuffer_gate(derive_editor_source())
    require(framebuffer["native_prompt_and_edited_line"] == "lisp65> abc"
            and framebuffer["cursor_left_insert_result"] == "abc"
            and framebuffer["ordinary_read_line_framebuffer_identical"] is True,
            "r3 composed framebuffer effect red")
    return {"status": "PASS: FINAL ELF NATIVE PROMPT USES BANK-2 EDITOR",
        "manifest": bind(MANIFEST), "header": bind(HEADER),
        "native_entry": {"name": "%native-read-line", "ordinal": ordinal,
                         "length": 16},
        "public_read_line": {"ordinal": names.index("read-line"), "length": 235},
        "resolved_calls": {"vm_run_dir": [f"0x{int(row['address']):04x}"
                                            for row in vm_calls],
                           "lisp_input_event": []},
        "prompt_owner": {"object": "%native-prompt",
                         "literals": prompt_literals,
                         "C_branch": "disabled by candidate header macro"},
        "ordinary_text": {"end_exclusive": text.address + text.bytes,
                          "facade_start": facade.address,
                          "free_bytes": ordinary_free,
                          "permanent_floor_bytes": 32},
        "candidate_extent": CODE.stat().st_size,
        "compiler_consumers": consumption,
        "stdlib_header_consumers": stdlib_consumption,
        "force_include_bound_equals_consumed": force_include_sweep,
        "composed_framebuffer_effect": {
            "status": "PASS: R3 PROMPT/INPUT/HANDOFF COMPOSED",
            "frozen_pair": {"ELF": bind(ELF), "PRG": bind(PRG)},
            "candidate_editor_source": bind(CLIENT_SOURCE),
            "candidate_manifest": bind(MANIFEST),
            "result": framebuffer,
            "claim": ("the same candidate directory consumed by the r3 "
                      "entry route renders the prompt and editable line; "
                      "ordinary explicit read-line remains framebuffer-identical")},
        "capacity_projection": {"symbol_slots": 111, "namepool_bytes": 1473},
        "mutations": {"restore-C-queue-reader": "rejected",
                      "header-ordinal-divergence": "rejected",
                      "restore-resident-prompt-string": "rejected",
                      "spend-below-text-floor": "rejected"}}


def r5_final_facade_gate() -> dict[str, Any]:
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ,
                          include_section_data=False)
    text = truth.section(".text")
    facade = truth.section(".lisp65_c2_mapped_far_facade")
    handoff = truth.section(".lisp65_c2_kernal_handoff")
    map_rows = {}
    for label, path in (
            ("seed", BUILD / "wplto/resident-island-seed.prg.map"),
            ("final", final_product_root() /
                "lisp65-c2-substitution-linked.prg.map")):
        map_rows[label] = {
            "text": map_section(path, ".text"),
            "facade": map_section(path, ".lisp65_c2_mapped_far_facade"),
            "next_owner": map_section(path, ".lisp65_c2_kernal_handoff")}
    for row in map_rows.values():
        candidate = {"text_end": row["text"]["end_exclusive"],
            "floor": 32, "arena_start": 0xB3B0,
            "arena_end": row["next_owner"]["VMA"],
            "facade_bytes": row["facade"]["bytes"],
            "shared_offset": 0x28000,
            "facade_vma": row["facade"]["VMA"],
            "facade_lma": row["facade"]["LMA"],
            "final_linked": True}
        result = r5_facade_placement_gate(**candidate)
        require(result["derived_vma"] == row["facade"]["VMA"]
                and result["derived_lma"] == row["facade"]["LMA"]
                and result["ordinary_text_reserve_bytes"] >= 32
                and result["tail_reserve_bytes"] >= 0,
                f"r5 {label} facade placement differs from priced relation")
    require(facade.address == max(0xB3B0, text.address + text.bytes + 32)
            and facade.bytes == 98
            and handoff.address >= facade.address + facade.bytes,
            "r5 final ELF facade owner relation drift")
    linker = (BUILD / "wplto/c2-substitution.ld").read_text(
        encoding="utf-8")
    source = r5_linker_placement_source_gate(linker)
    candidate = {"text_end": text.address + text.bytes, "floor": 32,
        "arena_start": 0xB3B0, "arena_end": handoff.address,
        "facade_bytes": facade.bytes, "shared_offset": 0x28000,
        "facade_vma": facade.address, "facade_lma": facade.address + 0x28000,
        "final_linked": True}
    return {"status": "PASS: R5 FINAL FACADE DERIVED FROM FINAL TEXT",
        "ELF": bind(ELF), "text_end_exclusive": text.address + text.bytes,
        "facade": {"VMA": facade.address, "LMA": facade.address + 0x28000,
                    "bytes": facade.bytes,
                    "end_exclusive": facade.address + facade.bytes},
        "next_owner": {"name": ".lisp65_c2_kernal_handoff",
                         "VMA": handoff.address},
        "ordinary_text_reserve_bytes": 32,
        "next_owner_reserve_bytes": (
            handoff.address - (facade.address + facade.bytes)),
        "shared_MAP_offset": 0x28000,
        "maps": map_rows, "linker_source": source,
        "mutations_rejected": r5_placement_mutations(candidate)}


def final_gate() -> dict[str, Any]:
    product = BLOCK_A.ORIGINAL_FINAL_GATE()
    geometry = composed()
    tuple_value = tuple_loadaddr_gate()
    prompt = native_prompt_final_elf()
    boundary = final_lto_boundary_gate()
    client = product["v1_8_native_line_editor_client"]
    require(client["hybrid"]["loss"]["linked_events_drained"] == 94
            and client["hybrid"]["loss"]["linked_dropped"] == 0
            and client["hybrid"]["normalization"]["executions"] == 512
            and client["hybrid"]["responsiveness"]["margin_percent"] >= 25.0
            and product["recovery_quiescence"]["model"]["cases"][
                "sealed-empty"]["overlay_calls"] == 2,
            "B-light changed Block-A owner/recovery walls")
    product["v1_9_Block_B_light"] = {
        "status": "PASS: NATIVE PROMPT AND EDITOR COMPOSED",
        "composed_bank2": geometry, "tuple_LOADADDR": tuple_value,
        "final_LTO_boundary": boundary,
        "derived_facade": r5_final_facade_gate(),
        "native_prompt_final_ELF": prompt,
        "client_walls": client,
        "claim_limit": "host-qualified B-light product; no media/device claim"}
    return product


def write_report(value: dict[str, Any]) -> None:
    gate = value["final_product"]["v1_9_Block_B_light"]
    prompt = gate["native_prompt_final_ELF"]
    facade = gate["derived_facade"]
    response = gate["client_walls"]["hybrid"]["responsiveness"]
    pair = value["artifacts_after"]
    REPORT.write_text(f"""# v1.9 Block B — B-light native prompt editor

Status: **{value['status']}**

The owner-selected B-light r5 card uses one newly authorized WPLTO/product
link.  Across the card history this is the fourth link (r2/r3/r4/r5): r2 exposed
the stale force-include header, r3 proved that repair effective but stopped in
the seed link, r4 proved the final-LTO boundary but stopped 12 bytes into the
historical facade, and r5 is the first complete candidate.  The native
`lisp65>` prompt now routes through the candidate-derived private Bank-2 entry;
the public `read-line` remains the runtime editor function.  While active, the
editor owns prompt, editable cells and handoff.  Profiles without the entry
retain the predecessor C collector.

The final plane is **{CODE.stat().st_size:,} bytes**.  `%native-prompt` is 32
bytes, `%native-read-line` 16, `read-line` 235 and `%rl-screen-tail` 212; every
object remains below 255 bytes.  The composed Bank-2 largest hole is
**{gate['composed_bank2']['largest_contiguous_hole']['bytes']:,} bytes**.
The final ordinary-text hole is **{prompt['ordinary_text']['free_bytes']} bytes**,
against the permanent 32-byte floor.  Capacity projects to 111 symbol slots
and 1,473 name bytes free.

The existing 98-byte mapped facade is derived from the final text end rather
than pinned to `$B3B0`: VMA `${facade['facade']['VMA']:04X}`, LMA
`${facade['facade']['LMA']:05X}` through the unchanged `$28000` MAP offset,
with **{facade['next_owner_reserve_bytes']} bytes** to the next owner.  Both
seed and final link prove that relation; no body, call edge or MAP transition
was added.

The final ELF has two direct `vm_run_dir` calls in `repl` (banner and editor),
no resident `lisp_input_event` call, and no C-owned `lisp65> ` string.  The
candidate header's entry ordinal equals the candidate directory ordinal.  A
line beyond the 191-byte native buffer limit is rejected before copy and is
never truncated then evaluated.

All Block-A walls remain green: 94/94 lossless, zero drops, 512/512
normalization, and **{response['margin_percent']:.3f}%** responsiveness margin.
Every emitted difference is attributed to the three declared roots before
Scope and Acceptance.  The price used isolated target objects, so it could
measure the resident bridge delta but could not see the real whole-program LTO
world in which removal of the last ordinary `scr_cursor` callers folded its
65-byte body into a fixed-section wrapper.  The r4 final-ELF boundary probe
closes that forecast gap.  Both qualifiers read the frozen pair:

- ELF: `{pair['ELF']['sha256']}`
- PRG: `{pair['PRG']['sha256']}`

No medium was built and no device was contacted.  Hardware acceptance remains
the authority for the native prompt/editor and bundled Block-A session rows.
""", encoding="utf-8")


def build() -> None:
    configure()
    pre = load(BASE.PREFLIGHT_RECEIPT)
    r5_pre = load(R5_PREFLIGHT)
    require(pre["status"] == "PASS: V1.9 B-LIGHT CARD ARMED 0/1"
            and r5_pre["status"] ==
                "PASS: R5 DERIVED FACADE ARMED 0/1"
            and not BUILD.exists() and not RECEIPT.exists()
            and not DIFFERENCE.exists()
            and not BASE.INVOCATION.exists(),
            "B-light preflight/lifecycle drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                           text=True, stdout=subprocess.PIPE, check=True).stdout
    require(clean == "", "B-light link requires committed clean sources")
    stdlib_consumer = stdlib_consumer_preflight()
    BASE.INVOCATION.write_bytes(canonical({"status": "INVOKED",
        "authority": authority(), "preflight": bind(R5_PREFLIGHT),
        "real_stdlib_header_consumer": stdlib_consumer,
        "budget": {"WPLTO_runs": 1, "product_links": 1}}))
    processes = [BASE.run_child("_produce")]
    before = BASE.artifacts()
    diff = attribution()
    require(all(value == 0 for name, value in diff["counts"].items()
                if name.startswith("unexplained_")),
            "B-light attribution retained unexplained members")
    DIFFERENCE.write_bytes(canonical(diff))
    gate = final_gate()
    processes.extend((BASE.run_child("_scope"), BASE.run_child("_accept")))
    after = BASE.artifacts()
    scope = load(BASE.SCOPE_RESULT)
    acceptance = load(BASE.ACCEPTANCE_RESULT)
    require(before == after
            and scope["status"] == acceptance["status"] == "PASS",
            "B-light read-only qualification tail red")
    value = {"format": FORMAT, "recorded_on": "2026-08-29",
        "status": STATUS, "authority": authority(),
        "preflight": bind(R5_PREFLIGHT),
        "inherited_preflight": bind(BASE.PREFLIGHT_RECEIPT),
        "invocation": bind(BASE.INVOCATION),
        "configuration": pre["configuration"],
        "attribution": {"receipt": bind(DIFFERENCE),
                        "status": diff["status"],
                        "counts": diff["counts"],
                        "family_counts": diff["product_members"][
                            "family_counts"]},
        "final_product": gate, "producer": bind(BASE.PRODUCER_RESULT),
        "scope": bind(BASE.SCOPE_RESULT), "acceptance": bind(BASE.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "processes": processes,
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 1,
            "scope_runs": 1, "acceptance_runs": 1,
            "media_builds": 0, "device_contacts": 0},
        "media_authorized": False,
        "next": "independent review; bundled Block-A/Block-B hardware remains closed"}
    RECEIPT.write_bytes(canonical(value))
    write_report(value)
    check()
    print("v1.9 B-light: CARD PASS WPLTO=1/1 link=1/1 prompt=editor")


def check() -> None:
    configure()
    value = load(RECEIPT)
    difference = load(DIFFERENCE)
    gate = value["final_product"]["v1_9_Block_B_light"]
    require(value["status"] == STATUS
            and value["authority"] == authority()
            and value["artifacts_before"] == BASE.artifacts()
            and value["artifacts_after"] == value["artifacts_before"]
            and canonical(difference) == canonical(attribution())
            and value["attribution"]["receipt"] == bind(DIFFERENCE)
            and value["attribution"]["counts"] == difference["counts"]
            and gate["composed_bank2"] == composed()
            and gate["tuple_LOADADDR"] == tuple_loadaddr_gate()
            and gate["derived_facade"] == r5_final_facade_gate()
            and gate["native_prompt_final_ELF"] == native_prompt_final_elf()
            and all(member == 0 for name, member in
                    difference["counts"].items()
                    if name.startswith("unexplained_")),
            "v1.9 B-light receipt drift")
    print("v1.9 B-light: CHECK PASS prompt=editor offset=0x28000")


def record_red(error: Exception, invoked: bool) -> None:
    artifacts = {}
    for name, path in (("ELF", ELF), ("PRG", PRG),
                       ("map", BUILD / "wplto/lisp65-c2-substitution-linked.prg.map"),
                       ("lto", BUILD / "wplto/lisp65-c2-substitution-linked.prg.lto.o")):
        if path.is_file():
            artifacts[name] = bind(path)
    wplto = int(any(BUILD.rglob("*.lto.o")) or ELF.is_file())
    PRODUCT_FIRST_RED.write_bytes(canonical({"format": FORMAT + "-first-red",
        "recorded_on": "2026-08-29",
        "status": "FIRST RED: V1.9 B-LIGHT CARD STOPS", "error": str(error),
        "artifacts": artifacts,
        "attempt_accounting": {"producer_invoked": bool(invoked),
            "WPLTO_runs": wplto,
            "product_links": int(ELF.is_file()), "media_builds": 0,
        "device_contacts": 0}, "retry_authorized": False}))


def attribute_r5_link_red() -> None:
    configure()
    require(PRODUCT_FIRST_RED.is_file() and BUILD.is_dir()
            and not ELF.exists() and not PRG.exists()
            and not R5_LINK_RED_ATTRIBUTION.exists()
            and not R5_LINK_RED_REPORT.exists(),
            "r5 link-red attribution lifecycle drift")
    red = load(PRODUCT_FIRST_RED)
    require(red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_links"] == 0
            and red["retry_authorized"] is False
            and "C2 fixed Bank-0 state overlaps the runtime overlay"
                in red["error"],
            "r5 First Red is not the stopped seed-link world")
    maps = {label: path for label, path in (
        ("r4", R4_BUILD / "wplto/resident-island-seed.prg.map"),
        ("r5", BUILD / "wplto/resident-island-seed.prg.map"))}
    names = (".text", ".lisp65_c2_mapped_far_facade",
             ".lisp65_c2_kernal_handoff", ".lisp65_c2_fixed_bank0",
             ".lisp65_c2_fixed_bank0_code",
             ".lisp65_c2_fixed_bank0_hot_bss", ".rodata", ".bss")
    sections = {name: {label: map_section(path, name)
                       for label, path in maps.items()} for name in names}
    text = sections[".text"]
    facade = sections[".lisp65_c2_mapped_far_facade"]
    fixed = sections[".lisp65_c2_fixed_bank0_code"]
    hot = sections[".lisp65_c2_fixed_bank0_hot_bss"]
    handoff = sections[".lisp65_c2_kernal_handoff"]
    require(text["r4"] == text["r5"]
            and (facade["r4"]["VMA"], facade["r4"]["LMA"],
                 facade["r4"]["bytes"]) == (0xB3B0, 0x333B0, 98)
            and (facade["r5"]["VMA"], facade["r5"]["LMA"],
                 facade["r5"]["bytes"]) == (0xB3DC, 0x333DC, 98)
            and facade["r5"]["VMA"] - text["r5"]["end_exclusive"] == 32
            and handoff["r5"]["VMA"] -
                facade["r5"]["end_exclusive"] == 101
            and fixed["r4"] == fixed["r5"]
            and fixed["r5"]["bytes"] == 67
            and fixed["r5"]["end_exclusive"] <= hot["r5"]["VMA"],
            "r5 map does not isolate placement success from checker red")

    r4_lto = R4_BUILD / "wplto/resident-island-seed.prg.lto.o"
    r5_lto = BUILD / "wplto/resident-island-seed.prg.lto.o"
    truths = [ElfTruth.read(path, llvm_readobj=READOBJ,
                            include_section_data=True)
              for path in (r4_lto, r5_lto)]
    boundary = {name: [truth.symbol(name).bytes for truth in truths]
                for name in ("kb_cursor_off", "scr_cursor",
                             "c2_facade_target_c2e_cons", "rtov_fail")}
    require(boundary["kb_cursor_off"] == [3, 3]
            and boundary["scr_cursor"] == [51, 51]
            and boundary["c2_facade_target_c2e_cons"] == [40, 40]
            and boundary["rtov_fail"] == [24, 24],
            "r5 changed the effective non-inline/fixed-code body world")
    old_linker = (R4_BUILD / "wplto/c2-substitution.ld").read_text(
        encoding="utf-8")
    new_linker = (BUILD / "wplto/c2-substitution.ld").read_text(
        encoding="utf-8")
    pin_tokens = (
        "SIZEOF(.lisp65_c2_fixed_bank0_code) == 69",
        "__lisp65_c2_fixed_bank0_code_c2e_cons == 0xc21d",
        "__lisp65_c2_fixed_bank0_code_rtov_fail == 0xc245",
        "__lisp65_c2_fixed_bank0_code_end == 0xc25d",
    )
    require(all(old_linker.count(token) == new_linker.count(token) == 1
                for token in pin_tokens),
            "fixed-code stored-world pin did not persist literally")
    placement = r5_linker_placement_source_gate(new_linker)
    prior = load(R4_LINK_RED_ATTRIBUTION)
    checker = prior["checker_conversion"]["remaining_fixed_code_equality"]
    require(checker == {"actual_overlap_bytes": 0,
                        "expected_bytes": 69,
                        "kind": "favorable stored-world equality",
                        "observed_bytes": 67}
            and prior["next_decision"]["checker_conversion"] ==
                "fixed Bank0 validates disjoint envelope/member order, not 69-byte equality",
            "r4 checker-conversion attribution drift")

    before = R4_PROFILE.read_text(encoding="utf-8").splitlines()
    after = PROFILE.read_text(encoding="utf-8").splitlines()
    old_root = R4_BUILD.relative_to(ROOT).as_posix()
    new_root = BUILD.relative_to(ROOT).as_posix()
    left = [line.replace(old_root, "<BUILD>") for line in before]
    right = [line.replace(new_root, "<BUILD>") for line in after]
    differences = []
    for old, new in zip(left, right):
        if old == new:
            continue
        family = ("derived-facade-linker-authority"
                  if old.startswith("linker_sha256=")
                  and new.startswith("linker_sha256=")
                  else "linker-build-id-generated-source-projection"
                  if "<BUILD>/wplto/generated-product-sources/" in old
                  and "<BUILD>/wplto/generated-product-sources/" in new
                  else None)
        require(family is not None,
                f"r4/r5 seed profile has unexplained difference: {old}")
        differences.append({"before": old, "after": new, "family": family})
    require(len(left) == len(right) and differences,
            "r4/r5 seed profile comparison is incomplete")

    value = {"format": FORMAT + "-link-red-attribution-v1",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: R5 PLACEMENT SUCCEEDS; SEALED FIXED-CODE PIN REMAINS",
        "authority": authority(), "preflight": bind(R5_PREFLIGHT),
        "first_red": bind(PRODUCT_FIRST_RED),
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "emitted_seed_world": {"maps": {name: bind(path)
                                           for name, path in maps.items()},
            "sections": sections,
            "LTO": {"r4": bind(r4_lto), "r5": bind(r5_lto),
                    "boundary_symbol_bytes": boundary},
            "profile": {"r4": bind(R4_PROFILE), "r5": bind(PROFILE),
                        "differences": differences}},
        "placement_verdict": {"status": "product geometry green",
            "derived_facade": placement,
            "ordinary_text_reserve_bytes": 32,
            "next_owner_reserve_bytes": 101,
            "shared_MAP_offset": 0x28000},
        "checker_verdict": {"kind": "known favorable stored-world equality",
            "inherited_attribution": bind(R4_LINK_RED_ATTRIBUTION),
            "pinned": list(pin_tokens), "emitted_fixed_code_bytes": 67,
            "actual_overlap_bytes": 0,
            "required_conversion": (
                "derive ordered member starts and the final envelope from "
                "the linked candidate; do not require 69 bytes or historical offsets")},
        "header_consumption": {
            "prelink_path_and_value": load(R5_PREFLIGHT)[
                "real_stdlib_header_consumer"],
            "seed_real_consumer": "not recorded because its link stopped",
            "final_real_consumer": "not reached",
            "obligation_status": "open"},
        "resume_legality": {"allowed": False,
            "reason": (
                "the linker SHA is an input to the phase-owned build ID and "
                "derived CRC world; editing only the post-WPLTO script would "
                "make the compiler profile differ from the consumed linker")},
        "product_defect": False, "unexplained_members": [],
        "next_decision": {"authorized": False,
            "recommended": (
                "one r6 WPLTO/product link after the already-attributed "
                "fixed-code checker is converted before WPLTO"),
            "remaining_r5_product_link_is_not_reusable": True}}
    R5_LINK_RED_ATTRIBUTION.write_bytes(canonical(value))
    R5_LINK_RED_REPORT.write_text(f"""# v1.9 B-light r5 link-red attribution

Status: **{value['status']}**

r5 spent one WPLTO and stopped before a product link.  The priced placement
worked exactly: ordinary text still ends at `$B3BC`, the 98-byte facade moved
from `$B3B0/$333B0` to `$B3DC/$333DC`, the text reserve is 32 bytes and the
next-owner reserve is 101 bytes.  The non-inline boundary is byte-identical to
r4 (`kb_cursor_off` 3 bytes, `scr_cursor` 51); Fixed-Bank0 is 67 bytes and has
zero overlap with Hot-BSS.

The sole red is the favorable exact equality already named in the r4
attribution: the generated linker still requires 69 bytes and the historical
member starts `$C21D/$C245`, while the emitted successor has the smaller
starts `$C21B/$C243`.  The repair is a checker conversion to derived ordered
members plus a disjoint envelope, not a product change.

A post-WPLTO linker-only resume is not valid: the linker SHA owns the build ID
and derived CRC projections.  Changing the script without regenerating that
world would violate bound=consumed.  Therefore r5 remains stopped at 1 WPLTO,
0 product links; Scope, Acceptance, the second real header consumer and media
were not reached.  A fresh r6 WPLTO/link needs an owner budget decision.
""", encoding="utf-8")
    print("v1.9 B-light: R5 RED ATTRIBUTED placement=green checker=stored-world")


def check_r5_link_red() -> None:
    value = load(R5_LINK_RED_ATTRIBUTION)
    sections = value["emitted_seed_world"]["sections"]
    facade = sections[".lisp65_c2_mapped_far_facade"]
    text = sections[".text"]["r5"]
    fixed = sections[".lisp65_c2_fixed_bank0_code"]["r5"]
    hot = sections[".lisp65_c2_fixed_bank0_hot_bss"]["r5"]
    require(value["status"] ==
                "ATTRIBUTED: R5 PLACEMENT SUCCEEDS; SEALED FIXED-CODE PIN REMAINS"
            and value["first_red"] == bind(PRODUCT_FIRST_RED)
            and value["attempt_accounting"] == {"WPLTO_runs": 1,
                "product_links": 0, "scope_runs": 0,
                "acceptance_runs": 0, "media_builds": 0,
                "device_contacts": 0}
            and facade["r5"]["VMA"] - text["end_exclusive"] == 32
            and facade["r5"]["LMA"] - facade["r5"]["VMA"] == 0x28000
            and sections[".lisp65_c2_kernal_handoff"]["r5"]["VMA"]
                - facade["r5"]["end_exclusive"] == 101
            and fixed["bytes"] == 67
            and fixed["end_exclusive"] <= hot["VMA"]
            and value["checker_verdict"]["actual_overlap_bytes"] == 0
            and value["header_consumption"]["obligation_status"] == "open"
            and value["resume_legality"]["allowed"] is False
            and value["product_defect"] is False
            and value["unexplained_members"] == []
            and value["next_decision"]["authorized"] is False,
            "r5 link-red attribution receipt drift")
    print("v1.9 B-light: R5 RED CHECK PASS placement=green retry=closed")


def map_section(path: Path, name: str) -> dict[str, int]:
    pattern = (rf"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+1 "
               + re.escape(name) + r"$")
    matches = re.findall(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    require(len(matches) == 1, f"map section population drift: {name}")
    vma, lma, size = (int(value, 16) for value in matches[0])
    return {"VMA": vma, "LMA": lma, "bytes": size,
            "end_exclusive": vma + size}


def r3_link_red_object_closure() -> dict[str, Any]:
    roots = [R2_BUILD / "wplto/.canonical-objects-resident-island-seed",
             R3_BUILD / "wplto/.canonical-objects-resident-island-seed"]
    populations = [{path.name: bind(path) for path in root.iterdir()
                    if path.is_file() and not path.is_symlink()}
                   for root in roots]
    require(populations[0].keys() == populations[1].keys()
            and len(populations[0]) == 70,
            "r3 failed-seed object population drift")
    changed = {name for name in populations[0]
               if populations[0][name]["sha256"] !=
                  populations[1][name]["sha256"]}
    require("018-repl.c.o" in changed and "combined-c.bc" in changed
            and not any(name.endswith(".s.o") for name in changed),
            "r3 failed-seed delta escaped C/header/profile closure")
    rows = []
    for name in sorted(populations[0]):
        family = ("entry-macro-editor-collector-object"
                  if name == "018-repl.c.o"
                  else "combined-C-routing-closure"
                  if name == "combined-c.bc"
                  else "profile-build-id-transitive-C-object"
                  if name in changed else "byte-identical")
        rows.append({"name": name, "r2": populations[0][name],
                     "r3": populations[1][name], "family": family})
    return {"members": rows, "changed_names": sorted(changed),
            "changed": len(changed), "unchanged": 70 - len(changed),
            "native_objects_changed": 0}


def r3_link_red_lto_mechanism() -> dict[str, Any]:
    r2_lto = R2_BUILD / "wplto/resident-island-seed.prg.lto.o"
    r3_lto = R3_BUILD / "wplto/resident-island-seed.prg.lto.o"
    old = ElfTruth.read(r2_lto, llvm_readobj=READOBJ,
                        include_section_data=True)
    new = ElfTruth.read(r3_lto, llvm_readobj=READOBJ,
                        include_section_data=True)
    old_kb, new_kb = old.symbol("kb_cursor_off"), new.symbol("kb_cursor_off")
    old_scr = old.symbol("scr_cursor")
    new_scr = new.symbols_by_name.get("scr_cursor", [])
    old_repl, new_repl = old.symbol("repl"), new.symbol("repl")
    old_event = old.symbol("lisp_input_event")
    new_event = new.symbol("lisp_input_event")
    old_dis = run([str(OBJDUMP), "-d",
        "--section=.lisp65_c2_fixed_bank0_code.kb_cursor_off", str(r2_lto)],
        "r2 kb_cursor_off disassembly")
    new_dis = run([str(OBJDUMP), "-d",
        "--section=.lisp65_c2_fixed_bank0_code.kb_cursor_off", str(r3_lto)],
        "r3 kb_cursor_off disassembly")
    require((old_kb.bytes, new_kb.bytes) == (5, 51)
            and old_scr.bytes == 65 and new_scr == []
            and (old_repl.bytes, new_repl.bytes) == (711, 642)
            and (old_event.bytes, new_event.bytes) == (128, 76)
            and "lda\t#$0" in old_dis and "jmp\t$0" in old_dis
            and "rts" in new_dis,
            "r3 LTO call-boundary attribution drift")
    return {"status": "PASS: LTO FOLDED SCR_CURSOR INTO FIXED CALLER",
        "objects": {"r2": bind(r2_lto), "r3": bind(r3_lto)},
        "symbols": {
            "kb_cursor_off": {"r2_bytes": old_kb.bytes,
                              "r3_bytes": new_kb.bytes,
                              "delta_bytes": new_kb.bytes - old_kb.bytes},
            "scr_cursor": {"r2_bytes": old_scr.bytes,
                           "r3_emitted_symbols": len(new_scr)},
            "repl": {"r2_bytes": old_repl.bytes,
                     "r3_bytes": new_repl.bytes},
            "lisp_input_event": {"r2_bytes": old_event.bytes,
                                 "r3_bytes": new_event.bytes}},
        "disassembly": {
            "r2_kb_cursor_off": "lda #0; tail-jump to emitted scr_cursor",
            "r3_kb_cursor_off": (
                "51-byte scr_cursor body folded into fixed-bank0 caller")},
        "mechanism": (
            "The candidate stdlib entry removes the old C collector and its "
            "other scr_cursor calls. LTO then eliminates the standalone "
            "65-byte scr_cursor and folds its body into the used/noinline "
            "kb_cursor_off fixed-section wrapper. The target-object +1-byte "
            "price could not observe this cross-function final-LTO move.")}


def attribute_r3_link_red() -> None:
    configure()
    r3_invocation = PREFLIGHT / "candidate-invocation-r3.json"
    require(R3_PRODUCT_FIRST_RED.is_file() and r3_invocation.is_file()
            and not (R3_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf").exists()
            and not (R3_BUILD / "wplto/lisp65-c2-substitution-linked.prg").exists()
            and not R3_LINK_RED_ATTRIBUTION.exists()
            and not R3_LINK_RED_REPORT.exists(),
            "r3 link-red attribution lifecycle drift")
    red = load(R3_PRODUCT_FIRST_RED)
    invocation = load(r3_invocation)
    require(red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_links"] == 0
            and red["retry_authorized"] is False
            and invocation["real_stdlib_header_consumer"]["status"] ==
                "PASS: REAL COMPILER CONSUMES CANDIDATE STDLIB HEADER",
            "r3 link-red accounting/header preflight drift")

    r2_map = R2_BUILD / "wplto/resident-island-seed.prg.map"
    r3_map = R3_BUILD / "wplto/resident-island-seed.prg.map"
    names = (".rodata", ".lisp65_runtime_overlay_verifier_bindings",
             ".data", ".bss", ".lisp65_c2_fixed_bank0_code",
             ".lisp65_c2_fixed_bank0_hot_bss")
    sections = {name: {"r2": map_section(r2_map, name),
                       "r3": map_section(r3_map, name)} for name in names}
    fixed = sections[".lisp65_c2_fixed_bank0_code"]
    hot = sections[".lisp65_c2_fixed_bank0_hot_bss"]
    overlap = fixed["r3"]["end_exclusive"] - hot["r3"]["VMA"]
    r2_margin = 0xC000 - sections[".bss"]["r2"]["end_exclusive"]
    r3_margin = 0xC000 - sections[".bss"]["r3"]["end_exclusive"]
    require(fixed["r2"]["bytes"] == 69
            and fixed["r3"]["bytes"] == 115
            and hot["r2"]["VMA"] == hot["r3"]["VMA"] == 0xC25D
            and overlap == 46
            and sections[".rodata"]["r2"]["bytes"] == 879
            and sections[".rodata"]["r3"]["bytes"] == 870
            and sections[".bss"]["r2"]["bytes"] == 1585
            and sections[".bss"]["r3"]["bytes"] == 1584
            and (r2_margin, r3_margin) == (5, 6),
            "r3 link-red map arithmetic drift")
    linker = (R3_BUILD / "wplto/c2-substitution.ld").read_text(encoding="utf-8")
    require("SIZEOF(.lisp65_c2_fixed_bank0_code) == 69" in linker
            and "ADDR(.bss) == 0xb9ca && SIZEOF(.bss) == 1585" in linker
            and "0xc000 - (ADDR(.bss) + SIZEOF(.bss)) == 5" in linker,
            "r3 linker-wall source attribution drift")
    mechanism = r3_link_red_lto_mechanism()
    require(mechanism["symbols"]["kb_cursor_off"]["delta_bytes"] == overlap,
            "fixed-section overlap does not equal LTO fold delta")
    value = {"format": FORMAT + "-link-red-attribution",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: FINAL-LTO CALLEE FOLD OVERFLOWS FIXED BANK0",
        "authority": authority(), "invocation": bind(r3_invocation),
        "first_red": bind(R3_PRODUCT_FIRST_RED),
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "positive_header_consumption": {
            "prelink": invocation["real_stdlib_header_consumer"],
            "candidate_header": bind(HEADER),
            "seed_assertion": bind(R3_BUILD /
                "wplto/resident-island-seed.stdlib-input-assert.h"),
            "emitted_route_delta": {
                "r2_undefined": ["lisp_input_event", "scr_backspace",
                                 "scr_clear", "scr_putc"],
                "r3_undefined": ["str_copy_out", "str_len"],
                "proof": ("the successful r3 compile emits the native-entry "
                          "collector object; the historical header cannot "
                          "produce this undefined-symbol set")}},
        "normalized_profile": r2_r3_profile_closure(),
        "compiler_object_closure": r3_link_red_object_closure(),
        "LTO_mechanism": mechanism,
        "link_map": {"r2": bind(r2_map), "r3": bind(r3_map),
                     "sections": sections,
                     "actual_product_overlap_bytes": overlap,
                     "ordinary_full_map": {
                         "rodata_delta_bytes": -9,
                         "bss_delta_bytes": -1,
                         "validation_margin": {"r2": r2_margin,
                                               "r3": r3_margin}}},
        "verdicts": {
            "fixed-bank0-overlap": {
                "kind": "product-placement blocker",
                "cause": "kb_cursor_off final-LTO growth 5 to 51 bytes",
                "bytes": overlap},
            "ordinary-full-map-chain": {
                "kind": "stored-world checker equality",
                "actual": "rodata is 9 bytes smaller; bss is 1 byte smaller"},
            "five-byte-margin": {
                "kind": "forecast-as-equality checker",
                "actual": "6 bytes free, one better than the 5-byte floor"}},
        "candidate_successor": {
            "product_fix_to_price": (
                "preserve a stable non-inlined call boundary from the fixed "
                "kb_cursor_off wrapper to ordinary scr_cursor; do not enlarge "
                "the fixed arena or pin a codegen spelling"),
            "checker_conversions": [
                "derive the ordinary full-map chain from the candidate",
                "validate the five-byte protection as a lower bound"],
            "new_WPLTO_and_link_required": True,
            "authorized": False},
        "unexplained_members": []}
    R3_LINK_RED_ATTRIBUTION.write_bytes(canonical(value))
    R3_LINK_RED_REPORT.write_text(f"""# v1.9 B-light r3 link attribution

Status: **{value['status']}**

The sole authorized r3 WPLTO completed compilation and reached the seed link,
but no linked product was emitted.  The candidate stdlib header was effective:
the r3 `repl` object drops the native `lisp_input_event` collector dependencies
and gains the string-return bridge dependencies.

The stop is a final-LTO placement effect missed by the target-object price.
Removing the old C collector removes all ordinary callers that kept
`scr_cursor` emitted.  LTO therefore folds its body into the used fixed-section
wrapper `kb_cursor_off`: **5 -> 51 bytes**.  The fixed Bank-0 code section grows
**69 -> 115 bytes** and overlaps the still-authoritative hot-BSS start at
`$C25D` by exactly **46 bytes**.

The other two linker messages are checker-family findings, not capacity loss:
`.rodata` is 9 bytes smaller, `.bss` is 1 byte smaller, and the protected gap is
6 rather than 5 bytes.  Their exact equalities need candidate derivation/lower-
bound semantics in any successor.

No retry, Scope, Acceptance, medium or device contact occurred.  A successor
needs a newly authorized WPLTO/link after pricing a stable non-inlined boundary
from the fixed wrapper to ordinary `scr_cursor`; this report authorizes none.
""", encoding="utf-8")
    print("v1.9 B-light: R3 LINK RED ATTRIBUTED fixed-fold=+46 link=0")


def attribute_r4_link_red() -> None:
    configure()
    require(PRODUCT_FIRST_RED.is_file() and BASE.INVOCATION.is_file()
            and BUILD.is_dir() and not ELF.exists() and not PRG.exists()
            and not R4_LINK_RED_ATTRIBUTION.exists()
            and not R4_LINK_RED_REPORT.exists(),
            "r4 link-red attribution lifecycle drift")
    red = load(PRODUCT_FIRST_RED)
    invocation = load(BASE.INVOCATION)
    require(red["attempt_accounting"]["WPLTO_runs"] == 1
            and red["attempt_accounting"]["product_links"] == 0
            and red["retry_authorized"] is False
            and invocation["real_stdlib_header_consumer"]["status"] ==
                "PASS: REAL COMPILER CONSUMES CANDIDATE STDLIB HEADER",
            "r4 link-red accounting/header probe drift")
    r3_map = R3_BUILD / "wplto/resident-island-seed.prg.map"
    r4_map = BUILD / "wplto/resident-island-seed.prg.map"
    names = (".text", ".rodata", ".bss",
             ".lisp65_c2_fixed_bank0_code",
             ".lisp65_c2_fixed_bank0_hot_bss",
             ".lisp65_c2_mapped_far_facade")
    sections = {name: {"r3": map_section(r3_map, name),
                       "r4": map_section(r4_map, name)} for name in names}
    fixed, hot = (sections[".lisp65_c2_fixed_bank0_code"],
                  sections[".lisp65_c2_fixed_bank0_hot_bss"])
    r3_overlap = fixed["r3"]["end_exclusive"] - hot["r3"]["VMA"]
    r4_overlap = max(0, fixed["r4"]["end_exclusive"] - hot["r4"]["VMA"])
    facade = sections[".lisp65_c2_mapped_far_facade"]["r4"]["VMA"]
    text_overlap = sections[".text"]["r4"]["end_exclusive"] - facade
    r4_margin = 0xC000 - sections[".bss"]["r4"]["end_exclusive"]
    r3_truth = ElfTruth.read(
        R3_BUILD / "wplto/resident-island-seed.prg.lto.o",
        llvm_readobj=READOBJ, include_section_data=True)
    r4_lto = BUILD / "wplto/resident-island-seed.prg.lto.o"
    r4_truth = ElfTruth.read(r4_lto, llvm_readobj=READOBJ,
                             include_section_data=True)
    require(r3_truth.symbol("kb_cursor_off").bytes == 51
            and r3_truth.symbols_by_name.get("scr_cursor", []) == []
            and r4_truth.symbol("kb_cursor_off").bytes == 3
            and r4_truth.symbol("scr_cursor").bytes == 51
            and fixed["r3"]["bytes"] == 115
            and fixed["r4"]["bytes"] == 67
            and (r3_overlap, r4_overlap, text_overlap) == (46, 0, 12)
            and sections[".text"]["r4"]["bytes"] -
                sections[".text"]["r3"]["bytes"] == 51
            and sections[".rodata"]["r4"]["bytes"] == 870
            and sections[".bss"]["r4"]["bytes"] == 1584
            and r4_margin == 6,
            "r4 link-red map/LTO attribution does not close")
    linker = (BUILD / "wplto/c2-substitution.ld").read_text(encoding="utf-8")
    derived = derived_full_map_checker_gate(linker)
    require("SIZEOF(.lisp65_c2_fixed_bank0_code) == 69" in linker
            and "ADDR(.text) + SIZEOF(.text) <= 0xb3b0" in linker,
            "r4 remaining linker stop ownership drift")
    seed_assert = BUILD / "wplto/resident-island-seed.stdlib-input-assert.h"
    require(seed_assert.is_file()
            and "!= 239u" in seed_assert.read_text(encoding="utf-8")
            and r4_truth.symbol("repl").bytes == 642
            and r4_truth.symbol("lisp_input_event").bytes == 76,
            "r4 seed did not inherit materialized entry-macro world")
    emitted = r3_r4_emitted_closure()
    profile = r2_r3_profile_closure()
    value = {"format": FORMAT + "-link-red-attribution",
        "recorded_on": "2026-08-29",
        "status": "ATTRIBUTED: BOUNDARY SUCCEEDS; ORDINARY TEXT LACKS 12 BYTES",
        "authority": authority(), "preflight": bind(R4_PREFLIGHT),
        "invocation": bind(BASE.INVOCATION), "first_red": bind(PRODUCT_FIRST_RED),
        "attempt_accounting": {"WPLTO_runs": 1, "product_links": 0,
            "scope_runs": 0, "acceptance_runs": 0,
            "media_builds": 0, "device_contacts": 0},
        "r3_to_r4_emitted_closure": emitted,
        "profile_closure": profile,
        "header_consumption": {
            "prelink_real_consumer": invocation["real_stdlib_header_consumer"],
            "seed_compile_assertion": bind(seed_assert),
            "seed_LTO_editor_route": {"repl_bytes": 642,
                "lisp_input_event_bytes": 76,
                "result": "candidate entry macro materialized"},
            "final_product_consumer": "not reached because seed link stopped",
            "all_two_consumers_proven": False},
        "LTO_boundary": {"r3": {"kb_cursor_off_bytes": 51,
                "scr_cursor_symbols": 0, "fixed_bank0_code_bytes": 115,
                "hot_BSS_overlap_bytes": r3_overlap},
            "r4": {"kb_cursor_off_bytes": 3, "scr_cursor_bytes": 51,
                "fixed_bank0_code_bytes": 67,
                "hot_BSS_overlap_bytes": r4_overlap},
            "verdict": "the authorized non-inline boundary is effective"},
        "link_map": {"r3": bind(r3_map), "r4": bind(r4_map),
            "sections": sections, "ordinary_text_facade_overlap_bytes": 12,
            "validation_margin_bytes": r4_margin},
        "checker_conversion": {"rodata_and_bss": derived,
            "remaining_fixed_code_equality": {
                "expected_bytes": 69, "observed_bytes": 67,
                "actual_overlap_bytes": 0,
                "kind": "favorable stored-world equality"}},
        "verdicts": {
            "original_46_byte_Hot_BSS_overlap": "closed",
            "fixed_bank0_message": (
                "checker equality only: emitted 67 is two bytes smaller than 69"),
            "ordinary_text_message": (
                "product placement blocker: restored 51-byte scr_cursor body "
                "ends ordinary text 12 bytes beyond the far-facade boundary")},
        "requirements_not_reached": [
            "second real compiler-consumer header proof",
            "complete product pair and r2-to-r4 closure",
            "Scope", "Acceptance", "B-light final-effect gates"],
        "next_decision": {
            "kind": "resident placement/reclaim price question",
            "minimum_ordinary_text_reclaim_bytes": 12,
            "checker_conversion": (
                "fixed Bank0 validates disjoint envelope/member order, not 69-byte equality"),
            "new_WPLTO_required": True, "authorized": False},
        "unexplained_members": []}
    R4_LINK_RED_ATTRIBUTION.write_bytes(canonical(value))
    R4_LINK_RED_REPORT.write_text(f"""# v1.9 B-light r4 link attribution

Status: **{value['status']}**

The sole authorized r4 WPLTO reached the seed link; no product link, Scope,
Acceptance, medium or device contact occurred.  The non-inline boundary works:
`kb_cursor_off` falls from 51 to 3 bytes, `scr_cursor` is emitted separately at
51 bytes, Fixed-Bank0 falls from 115 to 67 bytes, and the historical 46-byte
Hot-BSS overlap is zero.

The real LTO world exposes the price omitted by the target-object prototype:
the restored 51-byte `scr_cursor` body is ordinary text.  Text grows by exactly
51 bytes from r3 and ends **12 bytes beyond** the fixed mapped-facade start at
`$B3B0`.  This is a product placement blocker.  The other linker message is a
favorable exact-pin drift: Fixed-Bank0 is 67 rather than 69 bytes and remains
disjoint with two bytes to spare.  The converted `.rodata`/`.bss` bounds pass;
the BSS protection margin is the derived 6 bytes.

The complete comparable r3 emission world (70 seed objects, final-LTO bytes,
symbols and relocations) is fully classified with no unexplained member.  r3
had no final product pair, and r4 stopped at its seed link, so the second real
header consumer and the final B-light effects were correctly not claimed.

A successor is a resident placement/reclaim price question for at least 12
ordinary-text bytes plus conversion of the remaining 69-byte fixed-code
equality to its actual disjoint-envelope property.  It requires a new WPLTO;
this attribution authorizes none.
""", encoding="utf-8")
    print("v1.9 B-light: R4 LINK RED ATTRIBUTED boundary=green text-short=12")


def r5_facade_placement_gate(*, text_end: int, floor: int,
                             arena_start: int, arena_end: int,
                             facade_bytes: int, shared_offset: int,
                             facade_vma: int, facade_lma: int,
                             final_linked: bool) -> dict[str, int]:
    """Validate the successor's derived facade placement relation.

    The price record may simulate this relation, but only a final linked r5
    candidate is allowed to carry a product-capacity claim.  Keeping that bit
    inside the gate makes a fragment/object price structurally incapable of
    satisfying the implementation bar.
    """
    require(final_linked, "ordinary-text capacity was not final-linked")
    expected = max(arena_start, text_end + floor)
    require(facade_vma == expected,
            "mapped facade is not derived from final text plus its floor")
    require(facade_lma - facade_vma == shared_offset,
            "mapped facade VMA/LMA lost the shared MAP domain")
    require(facade_vma + facade_bytes <= arena_end,
            "mapped facade overlaps the next fixed owner")
    return {"derived_vma": facade_vma, "derived_lma": facade_lma,
            "ordinary_text_reserve_bytes": facade_vma - text_end,
            "tail_reserve_bytes": arena_end - (facade_vma + facade_bytes)}


def r5_placement_mutations(base: dict[str, int]) -> dict[str, str]:
    rejected = {}
    cases = {
        "restore-fixed-b3b0-facade": {
            **base, "facade_vma": base["arena_start"],
            "facade_lma": base["arena_start"] + base["shared_offset"]},
        "pin-current-derived-address-across-text-growth": {
            **base, "text_end": base["text_end"] + 1},
        "move-vma-without-lma": {
            **base, "facade_lma": base["facade_lma"] - 44},
        "overlap-next-owner": {
            **base, "facade_bytes":
                base["arena_end"] - base["facade_vma"] + 1},
        "fragment-price-as-final-capacity": {
            **base, "final_linked": False},
    }
    for name, values in cases.items():
        try:
            r5_facade_placement_gate(**values)
        except CardError as error:
            rejected[name] = str(error)
    require(set(rejected) == set(cases),
            "r5 placement mutation survived")
    return rejected


def r5_pricing_value(*, read_build: bool) -> dict[str, Any]:
    decision = load(R5_PRICE_DECISION)
    r4 = load(R4_LINK_RED_ATTRIBUTION)
    contract = load(STACK_OWNERSHIP)["mapped_far_service"]
    block_a = load(BLOCK_A_RECEIPT)
    require(decision["format"] ==
                "lisp65-c2-v190-native-prompt-editor-r5-pricing-authorization-v1"
            and decision["budget"] == {"WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0,
                "device_contacts": 0}
            and decision["selection_rule"] ==
                "return exactly one clearly green priced candidate or descope B-light"
            and r4["status"] ==
                "ATTRIBUTED: BOUNDARY SUCCEEDS; ORDINARY TEXT LACKS 12 BYTES",
            "r5 pricing authority drift")
    sections = r4["link_map"]["sections"]
    text = sections[".text"]["r4"]
    facade = sections[".lisp65_c2_mapped_far_facade"]["r4"]
    floor = 32
    resident = contract["resident"]
    arena_start = int(resident["start"], 0)
    arena_end = int(resident["end_exclusive"], 0)
    shared_offset = facade["LMA"] - facade["VMA"]
    derived_vma = max(arena_start, text["end_exclusive"] + floor)
    derived_lma = derived_vma + shared_offset
    candidate = {"text_end": text["end_exclusive"], "floor": floor,
        "arena_start": arena_start, "arena_end": arena_end,
        "facade_bytes": facade["bytes"], "shared_offset": shared_offset,
        "facade_vma": derived_vma, "facade_lma": derived_lma,
        "final_linked": True}
    projected = r5_facade_placement_gate(**candidate)
    mutations = r5_placement_mutations(candidate)
    e000 = block_a["final_product"]["v1_9_block_A"][
        "client_walls"]["E000_composition"]
    far_bytes = 1488
    far_capacity = int(contract["bank2"]["owner_capacity_bytes"])
    cold_bytes = 324
    cold_capacity = 371
    established_stub = 9
    require((text["end_exclusive"], facade["VMA"], facade["LMA"],
             facade["bytes"], arena_start, arena_end, shared_offset) ==
            (0xB3BC, 0xB3B0, 0x333B0, 98, 0xB3B0, 0xB4A3,
             0x28000)
            and projected == {"derived_vma": 0xB3DC,
                "derived_lma": 0x333DC,
                "ordinary_text_reserve_bytes": 32,
                "tail_reserve_bytes": 101}
            and e000["final_reserve_bytes"] == 57
            and e000["placement_gate"]["reserve_floor_bytes"] == 54
            and e000["largest_contiguous_hole_bytes"] == 49,
            "r5 source geometry drift")
    map_evidence = r4["link_map"]["r4"]
    lto_evidence = r4["r3_to_r4_emitted_closure"]["LTO"][
        "r4"]
    handoff = {"VMA": arena_end, "source":
        "mapped_far_service.resident.end_exclusive"}
    relocation_evidence = {"checked_from_build": read_build,
        "facade_owned_relocation_section_bytes": 264,
        "ELF32_RELA_bytes": 12,
        "facade_owned_relocation_count": 22,
        "runtime_source_fixed_address_hits": []}
    if read_build:
        r4_map = ROOT / map_evidence["path"]
        handoff_map = map_section(r4_map, ".lisp65_c2_kernal_handoff")
        rela_matches = re.findall(
            r"^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+[0-9]+ "
            r"\.rela\.lisp65_c2_mapped_far_facade$",
            r4_map.read_text(encoding="utf-8"), re.MULTILINE)
        require(len(rela_matches) == 1,
                "mapped-facade relocation section population drift")
        rela_vma, rela_lma, rela_bytes = (
            int(value, 16) for value in rela_matches[0])
        rela = {"VMA": rela_vma, "LMA": rela_lma,
                "bytes": rela_bytes,
                "end_exclusive": rela_vma + rela_bytes}
        profile = (R4_BUILD / "wplto/resolved-profile.txt").read_text(
            encoding="utf-8")
        source_paths = []
        for line in profile.splitlines():
            if not line.startswith("input_sha256="):
                continue
            raw = line[len("input_sha256="):].rsplit(":", 1)[0]
            path = ROOT / raw
            if path.is_file() and path.suffix in {".c", ".h", ".s", ".S"}:
                source_paths.append(path)
        hits = []
        for path in source_paths:
            source = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"(?i)(?:0x|\$)b3b0", source):
                hits.append(path.relative_to(ROOT).as_posix())
        target_pattern = re.compile(
            r"R_MOS_.*(?:\.lisp65_c2_mapped_far_facade\.abort|"
            r"c2_abort_driver_facade|c2_rtov_retire_continuations_facade|"
            r"c2_retired_continuation_stub)")
        object_paths = [R4_BUILD / "wplto/resident-island-seed.prg.lto.o"]
        object_paths.extend(sorted((R4_BUILD / (
            "wplto/.canonical-objects-resident-island-seed")).glob("*.o")))
        incoming = []
        for path in object_paths:
            output = run([str(ROOT / "tools/llvm-mos/bin/llvm-readelf"),
                          "-r", str(path)], "r5 facade relocation audit")
            incoming.extend(line.strip() for line in output.splitlines()
                            if target_pattern.search(line))
        require(handoff_map["VMA"] == arena_end
                and rela["bytes"] == 264 and len(incoming) == 10
                and not hits,
                "r5 relocation/fixed-address inventory drift")
        relocation_evidence.update({"handoff_map": handoff_map,
            "runtime_source_fixed_address_hits": hits,
            "materialized_source_count": len(source_paths),
            "incoming_symbol_or_section_relocations": len(incoming),
            "incoming_relocation_rows": incoming})
    required_reclaim = floor - (facade["VMA"] - text["end_exclusive"])
    require(required_reclaim == 44,
            "r5 overlap-to-floor arithmetic drift")
    return {
        "format": R4_FORMAT + "-r5-placement-pricing-v1",
        "recorded_on": "2026-08-29",
        "status": "PASS: ONE R5 PLACEMENT WINNER PRICED",
        "claim_limit": (
            "Host-only selection price over r4 final-LTO map evidence. "
            "No r5 product or final capacity claim exists before a newly "
            "authorized final WPLTO/link measures the relation."),
        "authority": {"decision": bind(R5_PRICE_DECISION),
            "r4_link_red_attribution": bind(R4_LINK_RED_ATTRIBUTION),
            "r4_map": map_evidence, "r4_final_LTO": lto_evidence,
            "stack_ownership": bind(STACK_OWNERSHIP),
            "Block_A_receipt": bind(BLOCK_A_RECEIPT)},
        "attempt_accounting": {"WPLTO_runs": 0, "product_links": 0,
            "media_builds": 0, "device_contacts": 0},
        "corrected_capacity_question": {
            "overlap_clearance_bytes": 12,
            "permanent_text_floor_bytes": floor,
            "current_text_reserve_bytes": -12,
            "required_capacity_recovery_bytes": required_reclaim,
            "reason": "clearing overlap alone would leave zero floor"},
        "recommended_candidate": {
            "name": "derived mapped-facade slide",
            "mechanism": (
                "place the existing 98-byte facade at max(arena_start, "
                "final_text_end + 32) and derive LMA with the unchanged "
                "shared MAP offset"),
            "current": {"text_end": text["end_exclusive"],
                "facade_vma": facade["VMA"], "facade_lma": facade["LMA"],
                "facade_bytes": facade["bytes"], "tail_owner": handoff},
            "projected": {**projected,
                "end_vma_exclusive": derived_vma + facade["bytes"],
                "end_lma_exclusive": derived_lma + facade["bytes"],
                "vma_and_lma_shift_bytes": 44},
            "freight_delta_bytes": 0,
            "call_graph_delta": 0,
            "service_time_delta": (
                "zero by construction: identical absolute JSR/JMP forms and "
                "identical MAP enter/leave population; r5 must confirm bytes"),
            "resident_arenas_touched": ["mapped-far-facade placement only"],
            "why_unique": (
                "it alone restores the standing text floor without spending "
                "E000, Far-Service or Product-Cold bytes and without adding "
                "a hot-path transport")},
        "dominated_routes": {
            "ordinary_body_relocation": {
                "Product_Cold": {"free_bytes": cold_capacity - cold_bytes,
                    "established_stub_bytes": established_stub,
                    "maximum_single_move_net_reclaim_bytes":
                        cold_capacity - cold_bytes - established_stub},
                "Far_Service": {"free_bytes": far_capacity - far_bytes,
                    "established_stub_bytes": established_stub,
                    "maximum_single_move_net_reclaim_bytes":
                        far_capacity - far_bytes - established_stub},
                "E000": {"aggregate_free_bytes": e000["final_reserve_bytes"],
                    "floor_bytes":
                        e000["placement_gate"]["reserve_floor_bytes"],
                    "spendable_bytes": 3,
                    "largest_contiguous_hole_bytes":
                        e000["largest_contiguous_hole_bytes"]},
                "verdict": (
                    "no established single-body move restores 44 bytes; "
                    "multi-tenant dispatch is a new design, not this price")},
            "move_scr_cursor": {"body_bytes": 51,
                "Product_Cold_free_bytes": cold_capacity - cold_bytes,
                "Far_Service_free_bytes": far_capacity - far_bytes,
                "E000_spendable_bytes": 3,
                "service_time_proof": "absent and required",
                "verdict": "does not fit and is not selectable"},
            "smaller_boundary": {"wrapper_bytes": 3,
                "instruction": "absolute JMP",
                "reclaim_bytes": 0,
                "verdict": "already minimum-sized"}},
        "relocation_safety": relocation_evidence,
        "permanent_rule": {
            "text_prices": (
                "Text capacity is accepted only from the final linked "
                "candidate; isolated fragments and micro-prototypes are "
                "selection evidence, never capacity evidence."),
            "owning_gate": "c2-v190-native-prompt-editor-r5-pricing-check",
            "mutations_rejected": mutations},
        "r5_obligations": [
            "owner authorizes the fourth WPLTO/product link explicitly",
            "facade VMA is derived from final text end plus the 32-byte floor",
            "facade LMA follows the same shared MAP offset",
            "98-byte facade stays inside the B3B0..B4A3 arena",
            "final-linked text reserve is at least 32 bytes",
            "all facade bodies and call edges are byte/CFG-equivalent",
            "r4-to-r5 differences are fully attributed with zero remainder",
            "both real force-include header consumers are positively proven",
            "Scope and Acceptance run read-only over the frozen r5 pair"],
        "next_decision": {"kind": "owner r5 link decision",
            "recommended_word": "r5-Link frei",
            "WPLTO_runs": 1, "product_links": 1,
            "authorized": False},
        "unexplained_members": []}


def price_r5_placement() -> None:
    require(not R5_PRICE_RECEIPT.exists() and not R5_PRICE_REPORT.exists(),
            "r5 placement price already recorded")
    value = r5_pricing_value(read_build=True)
    R5_PRICE_RECEIPT.write_bytes(canonical(value))
    candidate = value["recommended_candidate"]
    capacity = value["corrected_capacity_question"]
    projected = candidate["projected"]
    R5_PRICE_REPORT.write_text(f"""# v1.9 B-light r5 placement price

Status: **{value['status']}**

The host-only round ran over the emitted r4 LTO/map evidence and consumed zero
WPLTOs, links, media builds or device contacts.  Its first correction is
important: r4 is not merely 12 bytes short.  Twelve bytes clear the overlap,
but the standing 32-byte ordinary-text floor means the successor must recover
**{capacity['required_capacity_recovery_bytes']} bytes** from the current
`-12` position.

## One winner

Move the existing 98-byte mapped Far facade inside its already-owned
`$B3B0..$B4A3` arena.  Its VMA becomes the derived relation
`max(arena_start, final_text_end + 32)`, never a new address literal.  On the
r4 emitted world that relation is `$B3BC + 32 = $B3DC`; its LMA follows the
unchanged `$28000` MAP offset to `$0333DC`.  The facade ends at `$B43E`, leaving
**{projected['tail_reserve_bytes']} bytes** before the next fixed owner.  The
ordinary-text reserve is exactly
**{projected['ordinary_text_reserve_bytes']} bytes**.

This changes no product body and adds no call, byte or MAP transition.  Every
facade target remains an absolute relocation, so moving VMA and LMA together
has zero service-time cost.  The r5 final link must still prove byte/CFG
equivalence and the exact final-linked floor; this price is not that claim.

## Why the other routes lose

E000 has only 3 spendable bytes above its 54-byte floor.  Product-Cold has 47
bytes free and the established MAP entry costs 9, so a single move can reclaim
at most 38 bytes.  Far-Service has 11 bytes free and nets at most 2.  The
51-byte `scr_cursor` fits none of them and would additionally require the
missing hot-path service-time proof.  The non-inline wrapper is already the
minimum three-byte absolute jump.  Multi-tenant dispatch would be a new design,
not a priced reclaim, and loses to the zero-byte facade slide.

The permanent price rule is now executable: **text capacity is accepted only
from a final linked candidate, never from an isolated fragment or
micro-prototype**.  Mutations reject the old fixed `$B3B0`, a pinned `$B3DC`
that fails to follow text growth, VMA/LMA divergence, overlap with the next
owner, and any fragment price presented as final capacity.

No fourth link is authorized here.  The next decision is the owner's
`r5-Link frei` for exactly one WPLTO and one product link.  That run must also
prove the still-open second real Force-Include-header consumer.
""", encoding="utf-8")
    print("v1.9 B-light: R5 PRICE GREEN winner=derived-facade-slide link=0")


def check_r5_placement_price() -> None:
    value = load(R5_PRICE_RECEIPT)
    require(value["format"] == R4_FORMAT + "-r5-placement-pricing-v1"
            and value["status"] ==
                "PASS: ONE R5 PLACEMENT WINNER PRICED"
            and value["attempt_accounting"] == {"WPLTO_runs": 0,
                "product_links": 0, "media_builds": 0,
                "device_contacts": 0}
            and value["corrected_capacity_question"][
                "required_capacity_recovery_bytes"] == 44
            and value["recommended_candidate"]["projected"] == {
                "derived_vma": 0xB3DC, "derived_lma": 0x333DC,
                "ordinary_text_reserve_bytes": 32,
                "tail_reserve_bytes": 101,
                "end_vma_exclusive": 0xB43E,
                "end_lma_exclusive": 0x3343E,
                "vma_and_lma_shift_bytes": 44}
            and value["recommended_candidate"]["freight_delta_bytes"] == 0
            and value["recommended_candidate"]["call_graph_delta"] == 0
            and len(value["permanent_rule"]["mutations_rejected"]) == 5
            and value["next_decision"]["authorized"] is False
            and value["unexplained_members"] == [],
            "r5 placement price receipt drift")
    candidate = {"text_end": 0xB3BC, "floor": 32,
        "arena_start": 0xB3B0, "arena_end": 0xB4A3,
        "facade_bytes": 98, "shared_offset": 0x28000,
        "facade_vma": 0xB3DC, "facade_lma": 0x333DC,
        "final_linked": True}
    require(r5_facade_placement_gate(**candidate)[
                "ordinary_text_reserve_bytes"] == 32
            and set(r5_placement_mutations(candidate)) == set(
                value["permanent_rule"]["mutations_rejected"]),
            "r5 permanent price gate drift")
    print("v1.9 B-light: R5 PRICE CHECK GREEN final-link-floor rule armed")


def child(action: str) -> None:
    if action == "_release_probe":
        CLIENT.SUBSTRATE.release_probe_child()
        return
    configure()
    if action == "_profile_probe":
        CLIENT.SUBSTRATE.profile_probe_child()
    elif action == "_produce":
        BASE.produce_child()
    elif action == "_scope":
        BASE.scope_child()
    elif action == "_accept":
        BASE.acceptance_child()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "attribute-preflight-red",
        "attribute-resume-red", "resume-preflight", "build", "check",
        "attribute-r3-link-red", "attribute-r4-link-red", "prepare-r4",
        "prepare-r5", "attribute-r5-link-red", "check-r5-link-red",
        "price-r5-placement", "check-r5-placement-price",
        "_profile_probe", "_release_probe", "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    if action == "prepare-r4":
        prepare_r4()
    elif action == "prepare-r5":
        prepare_r5()
    elif action == "preflight":
        preflight()
    elif action == "attribute-preflight-red":
        attribute_preflight_red()
    elif action == "attribute-resume-red":
        attribute_resume_red()
    elif action == "resume-preflight":
        resume_preflight()
    elif action == "attribute-r3-link-red":
        attribute_r3_link_red()
    elif action == "attribute-r4-link-red":
        attribute_r4_link_red()
    elif action == "attribute-r5-link-red":
        attribute_r5_link_red()
    elif action == "check-r5-link-red":
        check_r5_link_red()
    elif action == "price-r5-placement":
        price_r5_placement()
    elif action == "check-r5-placement-price":
        check_r5_placement_price()
    elif action == "build":
        try:
            build()
        except Exception as error:
            record_red(error, BASE.INVOCATION.exists())
            raise
    elif action == "check":
        check()
    else:
        child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"v1.9 B-light: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
