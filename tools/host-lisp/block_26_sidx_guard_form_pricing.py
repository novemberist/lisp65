#!/usr/bin/env python3
"""Measure alternative Card-1 symbol guards without a product WPLTO/link."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import block_26_sidx_product_card as CARD  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
CARD_RECEIPT = ARCH / "block-2.6-card1-sidx-product-r2-receipt.json"
RECEIPT = ARCH / "block-2.6-card1-sidx-guard-form-pricing.json"
REPORT = ROOT / "docs/planning/2.6-card1-sidx-guard-form-pricing-report.md"
BUILD = ROOT / "build/2.6/card1-sidx-guard-form-pricing-r3"
WPLTO = ROOT / "build/2.6/card1-sidx-product-r2/wplto"
PREDECESSOR_WPLTO = ROOT / "build/c2.3/v2.0.0-release-card-r3/wplto"
CANONICAL = WPLTO / ".canonical-objects-lisp65-c2-substitution-linked"
PREDECESSOR_CANONICAL = (
    PREDECESSOR_WPLTO / ".canonical-objects-lisp65-c2-substitution-linked"
)
COMPILER = ROOT / "tools/llvm-mos/bin/mos-mega65-clang"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
LLVM_LINK = Path("/usr/bin/llvm-link")
FORMAT = "lisp65-block-2.6-card1-sidx-guard-form-pricing-v1"
AUTHORIZATION = "63dca58d"
SWAP_THRESHOLD = 20


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_bind(commit: str, path: Path) -> dict[str, Any]:
    """Bind a historical input in the card era, not the living work plan."""
    relative = path.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=ROOT,
        check=True, stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def normalized_ir(path: Path, output: Path) -> dict[str, Any]:
    """Compare frontend semantics without path-owned diagnostic metadata."""
    run([str(COMPILER), "-x", "ir", "-S", "-emit-llvm", str(path),
         "-o", str(output)], "frontend IR projection")
    text = output.read_text(encoding="utf-8")
    text = re.sub(r"^; ModuleID = .*$", "; ModuleID = <normalized>", text,
                  flags=re.MULTILINE)
    text = re.sub(r"^(!\d+ = !\{)i64 \d+(?:, i64 \d+)*(\})$",
                  r"\1i64 <inline-asm-source-location>\2", text,
                  flags=re.MULTILINE)
    raw = text.encode()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "excluded_metadata": ["ModuleID", "inline-asm-source-location"]}


def profile_features() -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in
            (WPLTO / "resolved-profile.txt").read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1, "Card-1 feature profile drift")
    return tuple(item for item in rows[0].split(",") if item)


def force_include_flags() -> list[str]:
    flags: list[str] = []
    for suffix in ("compiler-input-consumption.json",
                   "stdlib-input-consumption.json"):
        row = load(WPLTO / ("lisp65-c2-substitution-linked.prg." + suffix))
        flags.extend(str(item) for item in row["actual_force_include_flags"])
    for path in (
        WPLTO / "stage-config.h",
        WPLTO / "runtime-overlay.prepare.h",
        WPLTO / "resident-island.h",
        WPLTO / "error-text-table.h",
        WPLTO / "c2-kernal-window.generated.h",
    ):
        flags.extend(("-include", path.relative_to(ROOT).as_posix()))
    return flags


def compile_flags() -> list[str]:
    CARD.configure()
    artifacts = load(PRODUCT.resolved_product_artifacts_manifest())
    definitions = (
        *PRODUCT.definitions(artifacts),
        *PRODUCT.scoped_probe_definitions(profile_features()),
    )
    return [
        "-Oz", "-Wall", "-ffile-compilation-dir=.",
        "-fdebug-compilation-dir=.", "-fcoverage-compilation-dir=.",
        "-mllvm", "-rng-seed=0",
        *(f"-D{item}" for item in definitions),
        *force_include_flags(),
        "-I", "src", "-I", "scripts", "-I", "build/c2.2/substitution",
        "-I", WPLTO.relative_to(ROOT).as_posix(), "-I", "build/bytecode",
    ]


def replace_once(text: str, old: str, new: str, name: str) -> str:
    require(text.count(old) == 1, f"{name} source target drift")
    return text.replace(old, new, 1)


def variants(source: str) -> dict[str, str]:
    noinline = replace_once(
        source,
        "static uint8_t eval_symbol_arg_p(obj value) {",
        "static __attribute__((noinline)) uint8_t eval_symbol_arg_p(obj value) {",
        "noinline shared predicate",
    )
    cold_failure = replace_once(
        source,
        "static uint8_t eval_symbol_arg_p(obj value) {\n"
        "    if (is_sym(value)) return 1;\n"
        "    lisp_abort_static(LISP65_ERR_VM_TYPE, \"vm: type error\");\n"
        "    return 0;\n"
        "}",
        "static __attribute__((noinline, cold)) void eval_symbol_type_error(void) {\n"
        "    lisp_abort_static(LISP65_ERR_VM_TYPE, \"vm: type error\");\n"
        "}\n\n"
        "static uint8_t eval_symbol_arg_p(obj value) {\n"
        "    if (is_sym(value)) return 1;\n"
        "    eval_symbol_type_error();\n"
        "    return 0;\n"
        "}",
        "cold failure outline",
    )
    always_inline = replace_once(
        source,
        "static uint8_t eval_symbol_arg_p(obj value) {",
        "static __attribute__((always_inline)) uint8_t eval_symbol_arg_p(obj value) {",
        "always-inline control",
    )
    return {
        "accepted-inline-shared-predicate": source,
        "always-inline-control": always_inline,
        "noinline-shared-predicate": noinline,
        "cold-failure-outline": cold_failure,
    }


def canonical_c_objects() -> list[Path]:
    paths = sorted(CANONICAL.glob("[0-9][0-9][0-9]-*.c.o"))
    require(len(paths) == 46 and paths[10].name == "010-eval.c.o",
            "Card-1 canonical C-object population drift")
    return paths


def symbol_sizes(path: Path) -> dict[str, int]:
    rows: dict[str, int] = {}
    truth = ElfTruth.read(path, llvm_readobj=READOBJ)
    for symbol in truth.symbols:
        if (symbol.name and symbol.section != "Undefined"
                and symbol.symbol_type not in ("Section", "File")):
            require(symbol.name not in rows or rows[symbol.name] == symbol.bytes,
                    f"non-unique symbol size: {symbol.name}")
            rows[symbol.name] = symbol.bytes
    return rows


def compile_variant(name: str, source: str, flags: list[str]) -> dict[str, Any]:
    directory = BUILD / name
    directory.mkdir(parents=True)
    source_path = directory / "eval.c"
    source_path.write_text(source, encoding="utf-8")
    bitcode = directory / "eval.c.o"
    compile_source = (ROOT / "src/eval.c" if
                      name == "accepted-inline-shared-predicate" else source_path)
    run([str(COMPILER), *flags, "-c", compile_source.relative_to(ROOT).as_posix(),
         "-o", bitcode.relative_to(ROOT).as_posix()], f"{name} frontend")
    objects = canonical_c_objects()
    linked = directory / "combined-c.bc"
    run([str(LLVM_LINK), *(str(bitcode if index == 10 else path)
        for index, path in enumerate(objects)), "-o", str(linked)],
        f"{name} deterministic llvm-link")
    assembly = directory / "combined-c.s"
    run([str(COMPILER), "-target", "mos", "-Oz", "-x", "ir", "-S",
         str(linked), "-o", str(assembly)], f"{name} relocatable codegen")
    obj = directory / "combined-c.o"
    run([str(COMPILER), "-c", str(assembly), "-o", str(obj)],
        f"{name} assembly")
    symbols = symbol_sizes(obj)
    required = ("eval_v2_workbench_service", "eval")
    require(all(symbol in symbols for symbol in required),
            f"{name} carrier symbols absent")
    helpers = {key: value for key, value in symbols.items()
               if key in ("eval_symbol_arg_p", "eval_symbol_type_error")}
    carrier = sum(symbols[key] for key in required) + sum(helpers.values())
    return {
        "source": bind(source_path), "bitcode": bind(bitcode),
        "combined_bitcode": bind(linked), "object": bind(obj),
        "symbols": {key: symbols[key] for key in required},
        "outlined_helpers": helpers, "carrier_bytes": carrier,
    }


def existing_combined_measurement(root: Path, name: str) -> dict[str, Any]:
    directory = BUILD / name
    directory.mkdir(parents=True)
    combined = root / "combined-c.bc"
    assembly = directory / "combined-c.s"
    obj = directory / "combined-c.o"
    run([str(COMPILER), "-target", "mos", "-Oz", "-x", "ir", "-S",
         str(combined), "-o", str(assembly)], f"{name} existing codegen")
    run([str(COMPILER), "-c", str(assembly), "-o", str(obj)],
        f"{name} existing assembly")
    symbols = symbol_sizes(obj)
    sizes = {name: symbols[name] for name in
             ("eval_v2_workbench_service", "eval") if name in symbols}
    require(len(sizes) == 2, f"{name} calibration symbols absent")
    return {"combined_bitcode": bind(combined), "object": bind(obj),
            "symbols": sizes, "carrier_bytes": sum(sizes.values())}


def validate(value: dict[str, Any]) -> None:
    rows = value["variants"]
    require(
        value["format"] == FORMAT
        and value["authorization"] == AUTHORIZATION
        and value["threshold_bytes"] == SWAP_THRESHOLD
        and value["accounting"] == {"product_WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0}
        and value["frontend_reproduction"]["semantic_IR_byteidentical"] is True
        and value["calibration"]["final_link_delta_bytes"] == 68
        and value["calibration"]["relocatable_codegen_delta_bytes"] != 68
        and rows["always-inline-control"]["carrier_bytes"] ==
            rows["accepted-inline-shared-predicate"]["carrier_bytes"]
        and value["decision"]["selected"] ==
            "accepted-inline-shared-predicate"
        and value["decision"]["swap"] is False,
        "Card-1 guard-form pricing receipt drift",
    )
    best = min(row["carrier_bytes"] for row in rows.values())
    require(value["decision"]["best_measured_carrier_bytes"] == best
            and value["decision"]["proven_final_link_saving_bytes"] < SWAP_THRESHOLD,
            "Card-1 guard-form threshold decision drift")


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Card-1 guard pricing is one-shot")
    card = load(CARD_RECEIPT)
    plan = PLAN.read_text(encoding="utf-8")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", AUTHORIZATION, "HEAD"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    require(ancestry.returncode == 0
            and "saving of ≥ 20 bytes swaps the form" in plan,
            "Card-1 guard measurement authorization drift")
    require(card["status"] == "PASS: BLOCK 2.6 CARD 1 SIDX DOMAIN PRODUCT GREEN",
            "accepted Card-1 product absent")
    BUILD.mkdir(parents=True)
    flags = compile_flags()
    source = (ROOT / "src/eval.c").read_text(encoding="utf-8")
    rows = {name: compile_variant(name, text, flags)
            for name, text in variants(source).items()}
    original_bitcode = CANONICAL / "010-eval.c.o"
    frontend_reproduction = {
        "expected": bind(original_bitcode),
        "observed": rows["accepted-inline-shared-predicate"]["bitcode"],
    }
    frontend_reproduction["byteidentical"] = (
        frontend_reproduction["expected"]["sha256"] ==
        frontend_reproduction["observed"]["sha256"])
    expected_ir = normalized_ir(original_bitcode, BUILD / "accepted-original.ll")
    observed_ir = normalized_ir(
        BUILD / "accepted-inline-shared-predicate/eval.c.o",
        BUILD / "accepted-recompiled.ll")
    frontend_reproduction["normalized_expected_IR"] = expected_ir
    frontend_reproduction["normalized_observed_IR"] = observed_ir
    frontend_reproduction["semantic_IR_byteidentical"] = (
        expected_ir["sha256"] == observed_ir["sha256"])
    require(frontend_reproduction["semantic_IR_byteidentical"],
            "measurement frontend did not reproduce accepted eval semantics")
    predecessor = existing_combined_measurement(
        PREDECESSOR_CANONICAL, "calibration-predecessor")
    accepted = existing_combined_measurement(CANONICAL, "calibration-accepted")
    calibration_delta = accepted["carrier_bytes"] - predecessor["carrier_bytes"]
    for row in rows.values():
        row["saving_vs_accepted_relocatable_codegen"] = (
            rows["accepted-inline-shared-predicate"]["carrier_bytes"] -
            row["carrier_bytes"])
    # The bounded host lane deliberately does not spend a product WPLTO.  It
    # reproduces the exact frontend but overstates the accepted guard delta;
    # therefore it may reject alternatives, never project their saving onto
    # the final link.  No alternative has a proven final-link saving.
    decision = {
        "selected": "accepted-inline-shared-predicate",
        "swap": False,
        "best_measured_form": min(rows,
            key=lambda key: rows[key]["carrier_bytes"]),
        "best_measured_carrier_bytes": min(
            row["carrier_bytes"] for row in rows.values()),
        "proven_final_link_saving_bytes": 0,
        "reason": ("the exact frontend was reproduced, but the bounded "
            "relocatable codegen lane did not reproduce the 68-byte final-link "
            "delta; without an authorized product WPLTO no alternative proves "
            "the >=20-byte final-link threshold"),
    }
    value = {
        "format": FORMAT, "recorded_on": "2026-09-03",
        "status": "PASS: KEEP ACCEPTED INLINE GUARD FORM",
        "authorization": AUTHORIZATION, "threshold_bytes": SWAP_THRESHOLD,
        "inputs": {"plan": bind(PLAN), "card": bind(CARD_RECEIPT),
                   "source": bind(ROOT / "src/eval.c")},
        "frontend_reproduction": frontend_reproduction,
        "calibration": {
            "predecessor": predecessor, "accepted": accepted,
            "relocatable_codegen_delta_bytes": calibration_delta,
            "final_link_delta_bytes": card["final_product"]["final_emission"]
                ["eval_v2_workbench_service"]["delta_bytes"],
            "claim": "relocatable MOS codegen is not final-link byte truth",
        },
        "variants": rows, "decision": decision,
        "accounting": {"product_WPLTO_runs": 0, "product_links": 0,
                       "device_contacts": 0},
    }
    validate(value)
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    print("Block 2.6 Card 1 guard pricing: PASS keep=inline WPLTO=0 link=0")


def report(value: dict[str, Any]) -> str:
    rows = value["variants"]
    table = "\n".join(
        f"| `{name}` | {row['carrier_bytes']} | "
        f"{row['saving_vs_accepted_relocatable_codegen']:+d} |"
        for name, row in rows.items())
    return f"""# Block 2.6 Card 1 — guard-form measurement

Status: **{value['status']}**

The bounded measurement used the same llvm-mos frontend flags and reproduced
the accepted `eval.c` semantic IR byte-for-byte after excluding only the
output-owned ModuleID and inline-assembly source-location metadata. It then ran each form through a
deterministic combined-C relocatable MOS codegen lane; it emitted no product
ELF/PRG and consumed **0 WPLTO / 0 product links / 0 device contacts**.

| Form | measured carrier bytes | saving vs accepted lane |
|---|---:|---:|
{table}

The calibration is intentionally decisive: this lane measures
**{value['calibration']['relocatable_codegen_delta_bytes']} bytes** between the
predecessor and accepted guard worlds, while the real final product link
measured **{value['calibration']['final_link_delta_bytes']} bytes**. Therefore
the relocatable lane is not allowed to project a candidate saving onto the
final link. No alternative proves the owner-bound **{SWAP_THRESHOLD}-byte**
final-link threshold without another product WPLTO.

Decision: keep the accepted inline shared predicate. This is not an inference
that the alternatives cannot be smaller; it is the fail-closed result that
none has a qualifying *proven final-link saving* under the authorized
zero-product-build measurement round.
"""


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(value["inputs"] == {"plan": sealed_bind(AUTHORIZATION, PLAN),
        "card": bind(CARD_RECEIPT),
        "source": sealed_bind(AUTHORIZATION, ROOT / "src/eval.c")},
        "guard pricing input drift")
    print("Block 2.6 Card 1 guard pricing: CHECK PASS keep=inline WPLTO=0 link=0")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "frontend-not-reproduced": lambda row: row["frontend_reproduction"].update(
            {"semantic_IR_byteidentical": False}),
        "false-final-calibration": lambda row: row["calibration"].update(
            {"relocatable_codegen_delta_bytes": 68}),
        "threshold-lowered": lambda row: row.update({"threshold_bytes": 19}),
        "unproven-swap": lambda row: row["decision"].update(
            {"selected": "noinline-shared-predicate", "swap": True}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PricingError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "guard pricing mutation survived")
    print(f"Block 2.6 Card 1 guard pricing: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "check", "selftest"))
    action = parser.parse_args().action
    try:
        {"build": build, "check": check, "selftest": selftest}[action]()
    except (PricingError, OSError, subprocess.SubprocessError,
            json.JSONDecodeError) as error:
        print(f"Block 2.6 Card 1 guard pricing: RED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
