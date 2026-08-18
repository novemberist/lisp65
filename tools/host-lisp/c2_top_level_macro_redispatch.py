#!/usr/bin/env python3
"""Actual-LCC and publication gate for Link 95 macro redispatch."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import bytecode_p0_compiler as C


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-top-level-macro-publication.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-top-level-macro-publication-receipt.json"
)
FORMAT = "lisp65-c2.3-link95-top-level-macro-publication-receipt-v1"
RECORDED_ON = "2026-08-09"


class RedispatchError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RedispatchError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def git_bytes(commit: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return result.stdout


def git_bind(commit: str, relative: str) -> dict[str, Any]:
    raw = git_bytes(commit, relative)
    return {"commit": commit, "path": relative, "bytes": len(raw), "sha256": sha(raw)}


def validate_contract(value: dict[str, Any]) -> None:
    require(
        value.get("format") == "lisp65-c2-top-level-macro-redispatch-contract-v1",
        "contract identity drift",
    )
    require(value.get("scope") == (
        "Link 95 outer-macro redispatch with a product-published predicate"
    ),
            "contract scope drift")
    require(value.get("owner_commission") ==
            "eb732707880271b642f3f009299b4216f8700d15",
            "Link 95 owner commission drift")
    require(value.get("redispatch_first_red_commit") ==
            "d532562e6b27b96cb24baed1ac7754a89740e4c8",
            "Link 94 redispatch First Red authority drift")
    require(value.get("publication") == {
        "product_owned_helper": "%c2-top-level-macro-p",
        "forbidden_compiler_private_callee": "%lcc-macro-p",
        "replay_fixture_may_publish_undelivered_name": False,
    }, "Link 95 publication contract drift")
    sources = value.get("sources")
    require(isinstance(sources, dict) and set(sources) == {
        "compiler", "profile", "locality", "prelude", "product_runtime",
        "actual_lcc_binary",
    }, "contract source inventory drift")
    cases = value.get("cases")
    require(isinstance(cases, list) and len(cases) == 8,
            "actual-LCC case inventory drift")
    ids = [row.get("id") for row in cases]
    require(ids == [
        "macro-generated-defun", "macro-generated-defun-call",
        "macro-generated-defmacro", "macro-generated-defmacro-call",
        "nested-outer-macro-chain", "nested-outer-macro-chain-call",
        "macro-generated-top-level-progn", "macro-remains-expression",
    ], "actual-LCC case order/identity drift")
    require(
        value.get("walls") == {
            "resident_delta_bytes": 0,
            "maximum_bank2_delta_bytes": 256,
            "outer_expansion_only": True,
            "top_level_progn_redispatch": True,
            "expression_fallback_preserved": True,
        },
        "Link 95 walls drift",
    )


def source_text(value: dict[str, Any], relative: str, *, commit: str | None = None) -> str:
    del value
    raw = git_bytes(commit, relative) if commit else (ROOT / relative).read_bytes()
    return raw.decode("utf-8")


def candidate_runtime(value: dict[str, Any]) -> str:
    source = source_text(value, value["sources"]["product_runtime"])
    old = "(%lcc-macro-p (car form))"
    new = "(%c2-top-level-macro-p (car form))"
    anchor = (
        "(defun lcc-run (form)\n"
        "  (%c2-run-expanded (%c2-top-level-expand form)))"
    )
    helper = (
        "\n\n; Link-95 product-owned published macro predicate.\n"
        "(defun %c2-top-level-macro-p (op)\n"
        "  (if (symbolp op) (eq (function-kind op) 'macro) nil))"
    )
    require(source.count(old) == 1 and new not in source,
            "Link-95 predicate-call transform boundary drift")
    require(source.count(anchor) == 1 and "%c2-top-level-macro-p (op)" not in source,
            "Link-95 helper insertion boundary drift")
    return source.replace(old, new, 1).replace(anchor, anchor + helper, 1)


def preload_text(
    value: dict[str, Any], *, compiler_override: str | None = None,
    product_runtime_override: str | None = None,
    commission: bool = False,
) -> str:
    sources = value["sources"]
    commit = value["redispatch_first_red_commit"] if commission else None
    parts = [
        compiler_override if compiler_override is not None
        else source_text(value, sources["compiler"], commit=commit),
        source_text(value, sources["profile"], commit=commit),
        source_text(value, sources["locality"], commit=commit),
        source_text(value, sources["prelude"], commit=commit),
    ]
    runtime = (
        product_runtime_override if product_runtime_override is not None
        else source_text(value, sources["product_runtime"], commit=commit)
    )
    marker = "(defun %number->string-result"
    require(marker in runtime, "product-runtime host adapter boundary drift")
    # The host LCC lane owns the historical C1-shaped compiler object.  This
    # one-line adapter lets the exact delivered product lcc-run execute against
    # that compiler without substituting an abstract dispatcher model.
    parts.append("(defun %c2-compile-form (form) (%c1-compile-form form))")
    parts.append(runtime.split(marker, 1)[0])
    parts.extend(value["macro_preload"])
    return "\n".join(parts) + "\n"


def run_actual_lcc(
    value: dict[str, Any], *, compiler_override: str | None = None,
    product_runtime_override: str | None = None,
    commission: bool = False,
) -> list[dict[str, str]]:
    binary = ROOT / value["sources"]["actual_lcc_binary"]
    require(binary.is_file() and not binary.is_symlink(),
            f"actual-LCC binary absent: {binary}")
    with tempfile.TemporaryDirectory(prefix="link94-actual-lcc-", dir=ROOT / "build") as raw:
        work = Path(raw)
        forms_path = work / "forms.lisp"
        preload_path = work / "preload.lisp"
        forms_path.write_text(
            "\n".join(row["form"] for row in value["cases"]) + "\n",
            encoding="utf-8",
        )
        preload_path.write_text(
            preload_text(
                value, compiler_override=compiler_override,
                product_runtime_override=product_runtime_override,
                commission=commission,
            ),
            encoding="utf-8",
        )
        process = subprocess.run(
            [str(binary), "lcc", str(forms_path), "--preload", str(preload_path)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    require(process.returncode == 0,
            f"actual-LCC process red: rc={process.returncode} stderr={process.stderr.strip()}")
    lines = process.stdout.splitlines()
    require(len(lines) == len(value["cases"]),
            f"actual-LCC output cardinality drift: {lines}")
    rows: list[dict[str, str]] = []
    for case, line in zip(value["cases"], lines):
        prefix = case["form"] + " => "
        require(line.startswith(prefix), f"actual-LCC output identity drift: {line}")
        rows.append({
            "id": case["id"], "form": case["form"],
            "observed": line[len(prefix):],
        })
    return rows


def validate_current_execution(value: dict[str, Any], rows: list[dict[str, str]]) -> None:
    expected = {row["id"]: row["expected"] for row in value["cases"]}
    require(
        all(row["observed"] == expected[row["id"]] for row in rows),
        "actual lcc-run redispatch result drift: " + repr(rows),
    )


def validate_first_red(value: dict[str, Any], rows: list[dict[str, str]]) -> None:
    observed = {row["id"]: row["observed"] for row in rows}
    for case_id in (
        "macro-generated-defun", "macro-generated-defun-call",
        "macro-generated-defmacro", "macro-generated-defmacro-call",
        "nested-outer-macro-chain", "nested-outer-macro-chain-call",
        "macro-generated-top-level-progn",
    ):
        require(observed[case_id] == "!error:undefined-public-name",
                f"commissioned First Red no longer reproduced: {case_id}={observed[case_id]}")
    require(observed["macro-remains-expression"] == "5",
            "commissioned expression counterprobe drift")


def validate_source(value: dict[str, Any], compiler: str, runtime: str) -> dict[str, Any]:
    runtime_fragments = (
        "(defun %c2-top-level-macro-p (op)",
        "(if (symbolp op) (eq (function-kind op) 'macro) nil)",
        "(defun %c2-top-level-expand (form)",
        "(%c2-top-level-macro-p (car form))",
        "(%c2-top-level-expand (macroexpand-1 form))",
        "(defun %c2-top-level-run-forms (forms)",
        "(progn (lcc-run (car forms))",
        "(defun %c2-run-expanded (form)",
        "((if (consp form) (eq (car form) 'progn) nil)",
        "(%c2-run-expanded (%c2-top-level-expand form))",
    )
    commissioned_compiler = git_bytes(
        "d532562e6b27b96cb24baed1ac7754a89740e4c8",
        value["sources"]["compiler"],
    ).decode("utf-8")
    require(compiler == commissioned_compiler,
            "accepted 1.11 compiler carrier changed in Link 95")
    require(all(fragment in runtime for fragment in runtime_fragments),
            "product outer-macro/top-level redispatch source drift")
    require("%lcc-macro-p" not in runtime,
            "compiler-private macro predicate survived in product runtime")
    require("(t (lcc-install compiled 't))" in runtime,
            "post-expansion expression fallback drift")
    require("src/" not in " ".join(value["sources"].values()),
            "Link 95 contract acquired a resident source")
    return {
        "compiler_carrier_byteidentical_to_commission": True,
        "product_runtime_fragments": len(runtime_fragments),
        "product_owned_macro_predicate": "%c2-top-level-macro-p",
        "compiler_private_macro_predicate_absent": True,
        "outer_macro_expansion": "recursive-macroexpand-1-before-classification",
        "top_level_progn": "recursive-lcc-run-redispatch",
        "expression_fallback": "transient-lcc-install-name-t",
        "resident_delta_bytes": 0,
    }


def mutation_tests(value: dict[str, Any]) -> int:
    compiler_path = ROOT / value["sources"]["compiler"]
    runtime_path = ROOT / value["sources"]["product_runtime"]
    compiler = compiler_path.read_text(encoding="utf-8")
    runtime = candidate_runtime(value)
    mutations: list[tuple[str, str, bool]] = []

    def runtime_mutation(old: str, new: str) -> None:
        require(old in runtime, f"runtime mutation anchor absent: {old}")
        mutations.append((compiler, runtime.replace(old, new, 1), True))

    runtime_mutation(
        "(%c2-top-level-expand (macroexpand-1 form))",
        "(macroexpand-1 form)",
    )
    runtime_mutation(
        "(%c2-top-level-macro-p (car form))",
        "(%lcc-macro-p (car form))",
    )
    runtime_mutation("(eq (car form) 'progn)", "(eq (car form) 'begin)")
    runtime_mutation(
        "(%c2-run-expanded (%c2-top-level-expand form))",
        "(%c2-run-expanded form)",
    )
    runtime_mutation(
        "(defun %c2-run-expanded (form)",
        "(defun %c2-run-expanded-broken (form)",
    )
    runtime_mutation(
        "((if (consp form) (eq (car form) 'defmacro) nil)\n"
        "                  (%set-macro",
        "((if (consp form) (eq (car form) 'macro) nil)\n"
        "                  (%set-macro",
    )
    runtime_mutation(
        "((if (consp form) (eq (car form) 'defun) nil)\n"
        "                  (lcc-install compiled",
        "((if (consp form) (eq (car form) 'lambda) nil)\n"
        "                  (lcc-install compiled",
    )
    runtime_mutation("(t (lcc-install compiled 't))", "(t compiled)")

    rejected = 0
    for index, (bad_compiler, bad_runtime, execute) in enumerate(mutations):
        try:
            validate_source(value, bad_compiler, bad_runtime)
            if execute:
                validate_current_execution(
                    value, run_actual_lcc(
                        value, compiler_override=bad_compiler,
                        product_runtime_override=bad_runtime,
                    )
                )
        except RedispatchError:
            rejected += 1
            continue
        raise RedispatchError(f"Link 95 mutation accepted: {index}")
    require(rejected == len(mutations), "mutation rejection count drift")
    return rejected


def bank2_price(value: dict[str, Any]) -> dict[str, Any]:
    relative = value["sources"]["product_runtime"]
    source_rows = {
        "Link93_baseline": git_bytes(
            value["redispatch_first_red_commit"], relative
        ).decode("utf-8"),
        "Link95_candidate": candidate_runtime(value),
    }
    prices: dict[str, dict[str, int]] = {}
    ledger = C._abi_ledger("dialect-v2", None)
    for name, source in source_rows.items():
        names, objects = C.compile_program(
            source, C.prepare_heap([]), strict_arity=True,
            abi_profile="dialect-v2", abi_ledger=ledger,
            prebuilt_primitives=True,
        )
        prices[name] = {
            "objects": len(names),
            "encoded_code_object_bytes": sum(len(objects[item].encode()) for item in names),
        }
    delta = {
        key: prices["Link95_candidate"][key] - prices["Link93_baseline"][key]
        for key in prices["Link93_baseline"]
    }
    require(
        prices == {
            "Link93_baseline": {"objects": 21, "encoded_code_object_bytes": 891},
            "Link95_candidate": {"objects": 27, "encoded_code_object_bytes": 1099},
        }
        and delta == {"objects": 6, "encoded_code_object_bytes": 208},
        f"Link 95 Bank-2 price drift: prices={prices} delta={delta}",
    )
    limit = int(value["walls"]["maximum_bank2_delta_bytes"])
    require(delta["encoded_code_object_bytes"] <= limit,
            "Link 95 Bank-2 delta exceeds commissioned wall")
    baseline_static_bytes = 45794
    capacity = 65536
    return {
        "method": "strict dialect-v2 P0 CodeObject compilation of the complete eval runtime",
        "baseline": prices["Link93_baseline"],
        "candidate": prices["Link95_candidate"],
        "delta": delta,
        "maximum_delta_bytes": limit,
        "Link93_bank2_static_code_bytes": baseline_static_bytes,
        "Link93_bank2_headroom_bytes": capacity - baseline_static_bytes,
        "priced_Link95_bank2_headroom_bytes": (
            capacity - baseline_static_bytes - delta["encoded_code_object_bytes"]
        ),
        "resident_delta_bytes": 0,
    }


def build_receipt(value: dict[str, Any]) -> dict[str, Any]:
    sources = value["sources"]
    compiler = (ROOT / sources["compiler"]).read_text(encoding="utf-8")
    runtime = candidate_runtime(value)
    source_claim = validate_source(value, compiler, runtime)
    current = run_actual_lcc(value, product_runtime_override=runtime)
    validate_current_execution(value, current)
    historical = run_actual_lcc(value, commission=True)
    validate_first_red(value, historical)
    price = bank2_price(value)
    link93_receipt = ROOT / (
        "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.3-trace-core-abi-link93-receipt.json"
    )
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "HOST-GREEN; ACTUAL-LCC-REDISPATCH-AND-PUBLISHED-HELPER-PROVED",
        "scope": value["scope"],
        "authorities": {
            "contract": bind(CONTRACT),
            "owner_commission": git_bind(
                value["owner_commission"],
                "docs/planning/post-v1.4.0-direction-plan.md",
            ),
            "current_sources": {
                key: bind(ROOT / relative)
                for key, relative in sources.items()
                if key != "actual_lcc_binary"
            },
            "product_runtime_candidate": {
                "base": bind(ROOT / sources["product_runtime"]),
                "bytes": len(runtime.encode("utf-8")),
                "sha256": sha(runtime.encode("utf-8")),
                "transform": "replace-private-call-and-append-product-helper",
            },
            "actual_lcc_binary": bind(ROOT / sources["actual_lcc_binary"]),
            "Link93_product_baseline": bind(link93_receipt),
            "driver": bind(Path(__file__)),
        },
        "first_red": {
            "authority_commit": value["redispatch_first_red_commit"],
            "compiler": git_bind(
                value["redispatch_first_red_commit"], sources["compiler"]
            ),
            "product_runtime": git_bind(
                value["redispatch_first_red_commit"],
                sources["product_runtime"],
            ),
            "actual_lcc_rows": historical,
            "mechanism": (
                "the original form was classified before outer macro expansion; "
                "a generated definition was compiled as an ordinary expression"
            ),
        },
        "source_contract": source_claim,
        "actual_lcc_execution": {
            "lane": "compiled call of the real lcc-run through the LCC VM engine",
            "abstract_model": False,
            "cases": current,
            "case_count": len(current),
        },
        "freight": price,
        "mutations_rejected": mutation_tests(value),
        "claim_limit": (
            "This receipt proves the host carrier, product-runtime source ordering, "
            "and the product-owned predicate source. The packed-product callee closure "
            "is proved separately. It does not claim a linked Link-95 product or device result."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("selftest", "write", "check"))
    args = parser.parse_args()
    try:
        value = load(CONTRACT)
        validate_contract(value)
        if args.mode == "selftest":
            count = mutation_tests(value)
            print(f"c2-top-level-macro-redispatch: SELFTEST PASS mutations={count}")
            return 0
        receipt = build_receipt(value)
        if args.mode == "write":
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(receipt))
        else:
            require(RECEIPT.is_file(), f"receipt absent: {RECEIPT}")
            require(RECEIPT.read_bytes() == canonical(receipt),
                    "tracked Link 95 host receipt drift")
    except (RedispatchError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"c2-top-level-macro-redispatch: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "c2-top-level-macro-redispatch: PASS "
        f"cases={receipt['actual_lcc_execution']['case_count']} "
        f"mutations={receipt['mutations_rejected']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
