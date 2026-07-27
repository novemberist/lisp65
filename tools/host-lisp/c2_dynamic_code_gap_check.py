#!/usr/bin/env python3
"""Bind the prelink finding that C2 lacks a session-created code contract."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "config/c2-dynamic-code-gap-proposal.json"
DOCUMENT = ROOT / "docs/planning/c2.1-dynamic-code-addendum.md"
SESSION = ROOT / "config/c2-session-directory-proposal.json"
ROOTS = ROOT / "config/c2-gc-root-single-source-proposal.json"
CORE = ROOT / "config/c2-address-identity-contract.json"
PRODUCT = ROOT / "config/workbench-product-contract.json"
SEAMS = ROOT / "config/v11-c1-entry-seams.json"
FASL_CONTRACT = ROOT / "config/v11-m-transactional-fasl-contract.json"
SESSION_EXTENSION = ROOT / "config/c2-session-extension-contract.json"
FASL_EMITTER = ROOT / "lib/lcc-fasl.lisp"
LCC_INSTALL = ROOT / "src/lcc_install_overlay.c"
COMPILE_REPL = ROOT / "src/compile_repl.c"
L65M_COMMIT = ROOT / "src/l65m_commit_overlay.c"
SCOPE = ROOT / "docs/planning/v1.2-scope-memo.md"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2-dynamic-code-gap-receipt.json"
)


class GapError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GapError(message)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def source_texts() -> dict[str, str]:
    return {
        "fasl": FASL_EMITTER.read_text(encoding="utf-8"),
        "lcc_install": LCC_INSTALL.read_text(encoding="utf-8"),
        "compile_repl": COMPILE_REPL.read_text(encoding="utf-8"),
        "l65m_commit": L65M_COMMIT.read_text(encoding="utf-8"),
        "scope": SCOPE.read_text(encoding="utf-8"),
    }


def audit(proposal: dict[str, Any], texts: dict[str, str],
          product: dict[str, Any], seams: dict[str, Any],
          session: dict[str, Any], roots: dict[str, Any],
          core: dict[str, Any], fasl_contract: dict[str, Any]) -> dict[str, Any]:
    require(proposal.get("format") == "lisp65-c2-dynamic-code-gap-proposal-v1"
            and proposal.get("status") == "option-a-owner-approved-bounded-probe-authorized",
            "dynamic-code stop status drift")

    resident = set(product.get("delivery", {}).get("resident", []))
    workflows = set(product.get("workflows", []))
    require({"compile-string", "load-lib"} <= resident,
            "compiler/load surface is no longer product-resident")
    require({"lcc-compile-install", "compile-load-lib"} <= workflows,
            "compiler workflows missing from product contract")

    seam_names = [row.get("id") for row in seams.get("cases", [])]
    require(seam_names == ["lcc-run", "eval", "eval-buffer", "compile-string"],
            "public compiler seam list drift")
    compile_case = seams["cases"][-1]
    require(any("(load-lib \"c1seam\")" in form for form in compile_case.get("forms", [])),
            "compile-string persistence roundtrip no longer proves load-lib")

    require("Magic \"L65M\"" in texts["fasl"]
            and "(defun compile-string" in texts["fasl"]
            and "(%save-staged dst len)" in texts["fasl"],
            "current persistent compiler output is no longer bound as L65M")
    require(fasl_contract.get("transaction", {}).get("max_payload_bytes") == 8192,
            "persistent compile payload limit drift")
    for key in ("lcc_install", "compile_repl", "l65m_commit"):
        require("vm_dir_add(" in texts[key], f"dynamic publisher drift: {key}")

    recommended = session.get("recommended_contract", {})
    image_fields = recommended.get("image_record", {}).get("fields", [])
    entry_fields = recommended.get("entry_record", {}).get("fields", [])
    require("shelf_record_index_u8" in image_fields and "flags_u8_zero" in image_fields,
            "approved C2D image source identity changed")
    require(entry_fields == [
        "image_slot_u8", "flags_u8_zero", "entry_ordinal_u16",
        "code_length_u16", "literal_resolution_base_u16", "session_generation_u16"
    ], "approved C2D entry semantics changed")
    measured = session.get("measured_inputs", {})
    require(measured.get("product_images") == 6
            and measured.get("directory_entries") == 583
            and measured.get("directory_capacity") == 608,
            "static C2 composition arithmetic drift")
    require(measured.get("current_runtime_materializer_slices") == 28
            and measured.get("current_runtime_materializer_code_bytes") == 36744,
            "legacy materializer retirement arithmetic drift")

    selected_roots = roots.get("selected_candidate", {})
    require(selected_roots.get("root_value_storage") ==
            "one contiguous mutable C2D root_values array; the only stored obj representation for heap-valued resolutions",
            "B2 canonical root storage drift")
    require(selected_roots.get("immutable_membership_source") ==
            "The identity-bound C2I-v2 descriptor kind stream; kind 3 and kind 7 only",
            "B2 immutable root-membership source drift")

    staged = core.get("staged_swap", [])
    require(staged and staged[-1].get("product_decoder") ==
            "C2 direct decoder replaces and funds itself from the retired L65M materializer",
            "C2 sole-decoder substitution rule drift")
    require("No product candidate contains a dual decoder" in core.get("rollback_rule", ""),
            "no-dual-decoder rollback rule drift")
    require("all public compiler entry seams" in texts["scope"]
            and "persistence" in texts["scope"]
            and "pass against the new address model" in texts["scope"],
            "C2.2 compiler/persistence exit rule drift")

    facts = proposal.get("measured_facts", {})
    require(facts.get("immutable_product_images") == 6
            and facts.get("immutable_product_entries") == 583
            and facts.get("legacy_directory_capacity") == 608
            and facts.get("uncontracted_numeric_gap_if_misread_as_capacity") == 25,
            "proposal composition arithmetic drift")
    require(facts.get("c2d_v2_bytes") == 11048
            and facts.get("c2d_v2_bank5_headroom_bytes") == 39768,
            "proposal C2D-v2 arithmetic drift")
    require(facts.get("persistent_compile_max_payload_bytes") == 8192,
            "proposal persistent payload drift")
    require(facts.get("current_persistent_output_format") ==
            "L65M-v1 legacy container",
            "proposal persistent format drift")
    require(facts.get("public_compiler_entry_seams") == seam_names,
            "proposal compiler seam binding drift")
    require(facts.get("current_product_dynamic_publishers") == [
        "src/lcc_install_overlay.c -> vm_dir_add",
        "src/l65m_commit_overlay.c -> vm_dir_add"
    ] and facts.get("engine_compatibility_publisher") ==
            "src/compile_repl.c -> vm_dir_add",
            "proposal publisher classification drift")

    options = proposal.get("options", [])
    require([row.get("id") for row in options] == [
        "c2-session-extension-images", "mutable-session-code-lane",
        "legacy-l65m-transition-lane", "static-c2-product-without-compilation"
    ], "dynamic-code option closure drift")
    require([row.get("assessment") for row in options] == [
        "recommended", "fallback-needs-address-and-root-contract-amendment",
        "rejected", "rejected"
    ], "dynamic-code option assessment drift")
    require(len(options[0].get("required_contract_work", [])) == 6,
            "recommended contract work is incomplete")
    require(len(proposal.get("required_negative_fixtures_after_decision", [])) == 10,
            "dynamic-code negative matrix closure drift")
    require("bounded session-extension" in proposal.get("next_authorized_action", ""),
            "authorized next action drift")

    return {
        "immutable_images": 6,
        "immutable_entries": 583,
        "legacy_capacity": 608,
        "numeric_gap_not_capacity": 25,
        "product_dynamic_publishers": 2,
        "engine_compatibility_publishers": 1,
        "public_compiler_seams": len(seam_names),
        "persistent_payload_bytes": 8192,
        "legacy_materializer_slices": 28,
        "legacy_materializer_bytes": 36744,
        "negative_fixture_classes_required": 10,
    }


def selftest() -> list[str]:
    proposal = load(PROPOSAL)
    product = load(PRODUCT)
    seams = load(SEAMS)
    session = load(SESSION)
    roots = load(ROOTS)
    core = load(CORE)
    fasl_contract = load(FASL_CONTRACT)
    texts = source_texts()
    rejected: list[str] = []

    # A selftest must first prove that the unmodified witness is accepted;
    # otherwise one unrelated baseline failure could make every mutation look
    # correctly rejected.
    audit(proposal, texts, product, seams, session, roots, core, fasl_contract)

    mutations = []
    mutations.append(("product-surface", lambda p, t, pr, s, se, r, c, f:
                      pr["delivery"]["resident"].remove("compile-string")))
    mutations.append(("persistent-format", lambda p, t, pr, s, se, r, c, f:
                      t.__setitem__("fasl", t["fasl"].replace("Magic \"L65M\"", "Magic \"OTHER\"", 1))))
    mutations.append(("dynamic-publisher", lambda p, t, pr, s, se, r, c, f:
                      t.__setitem__("lcc_install", t["lcc_install"].replace("vm_dir_add(", "removed_dir_add(", 1))))
    mutations.append(("entry-source", lambda p, t, pr, s, se, r, c, f:
                      se["recommended_contract"]["entry_record"]["fields"].__setitem__(1, "flags_u8")))
    mutations.append(("dual-decoder", lambda p, t, pr, s, se, r, c, f:
                      c.__setitem__("rollback_rule", "mixed product allowed")))
    mutations.append(("composition", lambda p, t, pr, s, se, r, c, f:
                      p["measured_facts"].__setitem__("immutable_product_entries", 582)))
    mutations.append(("payload", lambda p, t, pr, s, se, r, c, f:
                      f["transaction"].__setitem__("max_payload_bytes", 8191)))

    for label, mutate in mutations:
        values = tuple(copy.deepcopy(value) for value in
                       (proposal, texts, product, seams, session, roots, core, fasl_contract))
        mutate(*values)
        try:
            audit(*values)
        except GapError:
            rejected.append(label)
    require(len(rejected) == len(mutations), f"mutations not rejected: {rejected}")
    return rejected


def collect() -> dict[str, Any]:
    proposal = load(PROPOSAL)
    measured = audit(proposal, source_texts(), load(PRODUCT), load(SEAMS),
                     load(SESSION), load(ROOTS), load(CORE), load(FASL_CONTRACT))
    rejected = selftest()
    return {
        "format": "lisp65-c2-dynamic-code-gap-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-19",
        "status": "option-a-owner-approved-bounded-probe-authorized",
        "claim_limit": proposal["claim_limit"],
        "bindings": {
            "proposal": bind(PROPOSAL),
            "document": bind(DOCUMENT),
            "verifier": bind(ROOT / "tools/host-lisp/c2_dynamic_code_gap_check.py"),
            "session_directory_contract": bind(SESSION),
            "single_source_root_contract": bind(ROOTS),
            "address_identity_contract": bind(CORE),
            "product_contract": bind(PRODUCT),
            "compiler_entry_seams": bind(SEAMS),
            "transactional_fasl_contract": bind(FASL_CONTRACT),
            "fasl_emitter": bind(FASL_EMITTER),
            "dynamic_publishers": [bind(LCC_INSTALL), bind(COMPILE_REPL), bind(L65M_COMMIT)],
            "scope_memo": bind(SCOPE),
            "session_extension_contract": bind(SESSION_EXTENSION),
        },
        "measured": measured,
        "verified": {
            "immutable_c2d_v2_proof_preserved": True,
            "real_product_substitution_link_run": False,
            "product_bytes_changed": 0,
            "capacity_deltas": "all-zero/not-run",
            "mixed_decoder_rejected": True,
            "static_only_product_rejected": True,
            "mutation_classes_rejected": rejected,
        },
        "next_authorized_action": proposal["next_authorized_action"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check", "selftest"), nargs="?", default="check")
    args = parser.parse_args()
    if args.mode == "selftest":
        rejected = selftest()
        print(f"c2-dynamic-code-gap: SELFTEST PASS mutations={len(rejected)}")
        return 0
    value = collect()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.mode == "write":
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(encoded, encoding="utf-8")
        action = "WROTE"
    else:
        require(RECEIPT.is_file() and RECEIPT.read_text(encoding="utf-8") == encoded,
                "dynamic-code gap receipt drift; regenerate with mode 'write'")
        action = "PASS"
    print("c2-dynamic-code-gap: "
          f"{action} static=6/583 product-publishers=2 engine-publishers=1 seams=4 "
          "product-link=stopped option=A-authorized")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GapError as exc:
        print(f"c2-dynamic-code-gap: FAIL: {exc}")
        raise SystemExit(1)
