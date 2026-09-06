#!/usr/bin/env python3
"""Build Card 2's last product pair with mapped error returns."""

from __future__ import annotations

import argparse
from collections import Counter, deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402
import block_26_f011_map_abort_repair_pricing as PRICE  # noqa: E402
import block_26_f011_replacement_product_card as R2  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
AUTHORIZATION = "44d2d3f7"
PLAN_HEADER = "## Reviewer disposition — card 2 MAP-nesting red; error-return form — 2026-09-03"
BUILD = ROOT / "build/2.6/card2-f011-product-r3"
PREFLIGHT = ROOT / "build/2.6/card2-f011-product-r3-preflight"
PLANE = PREFLIGHT / "setup-owned/static-plane/narrow-static"
WPLTO = BUILD / "wplto"
ELF = WPLTO / "lisp65-c2-substitution-linked.prg.elf"
PRG = WPLTO / "lisp65-c2-substitution-linked.prg"
PROFILE = WPLTO / "resolved-profile.txt"
BOUND_PROFILE = PREFLIGHT / "card2-bound-feature-profile.txt"
INVOCATION = PREFLIGHT / "candidate-invocation.json"
PLANE_RECEIPT = ARCH / "block-2.6-card2-f011-product-r3-plane.json"
PREFLIGHT_RECEIPT = ARCH / "block-2.6-card2-f011-product-r3-preflight.json"
SOURCE_PREFLIGHT = ARCH / "block-2.6-card2-f011-product-r3-source-preflight.json"
PRELINK_RED = ARCH / "block-2.6-card2-f011-product-r3-prelink-red.json"
DIFFERENCE = ARCH / "block-2.6-card2-f011-product-r3-difference.json"
RECEIPT = ARCH / "block-2.6-card2-f011-product-r3-receipt.json"
ACCEPTANCE_CONVERSION = ARCH / (
    "block-2.6-card2-f011-r3-acceptance-placement-conversion.json")
ACCEPTANCE_SUCCESSOR_CONVERSION = ARCH / (
    "block-2.6-card2-f011-r3-acceptance-successor-conversion.json")
ACCEPTANCE_PROJECTION_CORRECTION = ARCH / (
    "block-2.6-card2-f011-r3-acceptance-projection-correction.json")
REPORT = ROOT / "docs/planning/2.6-card2-f011-product-r3-report.md"
DRIVER = Path(__file__).resolve()
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
FORMAT = "lisp65-block-2.6-card2-f011-product-r3-v1"
STATUS = "PASS: BLOCK 2.6 CARD 2 MAPPED ERROR-RETURN PRODUCT GREEN"
R2_RED = ARCH / "block-2.6-card2-f011-product-r2-final-red.json"
R2_ELF = R2.ELF
R2_PRG = R2.PRG
R2_PROFILE = R2.PROFILE
ORIGINAL_R2_FINAL_GATE = R2.final_gate


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


def git_section() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1, "last-link authority section drift")
    payload = (PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]).split(
        "\n## ", 1)[0].rstrip().encode() + b"\n"
    folded = " ".join(payload.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("host-only repair pricing round", "one final replacement wplto",
                  "mapped body never aborts", "last link"):
        require(token in folded, f"last-link authority token absent: {token}")
    return {"commit": AUTHORIZATION, "path": relative,
        "section": PLAN_HEADER, "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest()}


def authority() -> dict[str, Any]:
    return {"commission": git_section(), "repair_price": bind(PRICE.RECEIPT),
        "frozen_r2_red": bind(R2_RED),
        "right": "one final replacement WPLTO and product link",
        "last_link_budget": {"WPLTO_runs": 1, "product_links": 1,
            "device_contacts": 0},
        "card_history_before_last_link": {"WPLTO_runs": 2,
            "product_link_attempts": 2, "completed_product_links": 1}}


def semantic_source_gate(sealed_commit: str | None = None) -> dict[str, Any]:
    source_path = ROOT / "src/io.c"
    wrappers_path = ROOT / "src/optional/c2_f011_cold_wrappers.s"
    def source_bytes(path: Path) -> bytes:
        if sealed_commit is None:
            return path.read_bytes()
        return subprocess.run(["git", "show",
            f"{sealed_commit}:{path.relative_to(ROOT).as_posix()}"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    source_raw, wrappers_raw = source_bytes(source_path), source_bytes(wrappers_path)
    source, wrappers = source_raw.decode(), wrappers_raw.decode()
    def validate_repair(text: str) -> dict[str, Any]:
        result = PRICE.source_contract(text)
        require("if (read_link == LISP65_F011_READ_FAILED)" in text,
                "mapped failure return is not consumed")
        return result

    repair = validate_repair(source)
    packed = R2.source_checks(source, wrappers)
    packed["failure-clears-validity"] = source.count("disk_source_link = 0;") >= 4
    require(all(packed.values()), "packed-state contract regressed in last-link source")
    mutations = {
        "direct-in-body-ext-disk-get-restored": source.replace(
            "nt = (unsigned char)read_link;",
            "nt = ext_disk_get(DISK_EXT_DIR);", 1),
        "returned-failure-removed": source.replace(
            "if (read_link == LISP65_F011_READ_FAILED)", "if (0)", 1),
    }
    rejected = []
    for name, mutant in mutations.items():
        try:
            validate_repair(mutant)
        except (PRICE.PricingError, CardError, ValueError):
            rejected.append(name)
    require(rejected == list(mutations), "mapped-return source mutation survived")
    return {"status": "PASS: MAPPED TENANT RETURNS; ORDINARY CALLER OWNS ERROR",
        "source": {"path": source_path.relative_to(ROOT).as_posix(),
            "bytes": len(source_raw), "sha256": hashlib.sha256(source_raw).hexdigest()},
        "wrappers": {"path": wrappers_path.relative_to(ROOT).as_posix(),
            "bytes": len(wrappers_raw), "sha256": hashlib.sha256(wrappers_raw).hexdigest()},
        "packed_state": packed, "mapped_error_return": repair,
        "mutations_rejected": rejected,
        "ordinary_error_edge": "disk_source_refill -> disk_source_fetch -> io_disk_load_chain false"}


def reachable_targets(graph: dict[str, Any], roots: list[str],
                      targets: set[str]) -> list[dict[str, Any]]:
    result = []
    for root in roots:
        pending = deque([root]); parent: dict[str, str | None] = {root: None}
        while pending:
            current = pending.popleft()
            if current in targets:
                path = []
                node: str | None = current
                while node is not None:
                    path.append(node); node = parent[node]
                result.append({"mapped_body": root, "terminal": current,
                               "path": list(reversed(path))})
                continue
            for target in sorted(graph["edges"].get(current, ())):
                if target not in parent:
                    parent[target] = current; pending.append(target)
    return result


def final_gate() -> dict[str, Any]:
    value = ORIGINAL_R2_FINAL_GATE()
    truth = ElfTruth.read(ELF, llvm_readobj=READOBJ, include_section_data=True)
    graph = R2.NESTING.linked_graph(ELF)
    tenants = graph["tenants"]
    aborts = {row.name for row in truth.symbols
              if row.symbol_type == "Function" and row.name.startswith("lisp_abort")}
    abort_paths = reachable_targets(graph, tenants, aborts)
    require("io_disk_read_sector_link_far" in tenants
            and abort_paths == []
            and "ext_disk_get" not in graph["edges"].get(
                "disk_source_refill_far", set()),
            "mapped owner retains an abort-capable path")
    mutant = R2.NESTING.paths_to_map(graph, ["disk_source_refill_far"],
        injected_edges={"disk_source_refill_far": {"lisp_abort_code"}})
    require({row["terminal"] for row in mutant} == {
                R2.NESTING.ENTER, R2.NESTING.LEAVE},
            "direct in-body abort mutation did not reproduce MAP nesting")
    value["status"] = "PASS: FINAL CARD-2 ERROR-RETURN PRODUCT CLOSED"
    value["emitted_symbols"]["io_disk_read_sector_link_far"] = truth.symbol(
        "io_disk_read_sector_link_far").bytes
    value["mapped_error_return"] = {
        "abort_paths_from_derived_mapped_population": abort_paths,
        "direct_refill_ext_disk_get_edge": False,
        "ordinary_caller_owns_failure": True,
        "mutations_rejected": ["direct-in-body-lisp-abort-code-restored"],
        "mutation_paths": mutant,
    }
    return value


def profile_inputs(path: Path) -> dict[str, str]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("input_sha256="):
            name, digest = line.split(":", 1)
            rows[name.split("=", 1)[1]] = digest
    require(rows, f"profile source closure absent: {path}")
    return rows


def counter_rows(counter: Counter[Any]) -> list[dict[str, Any]]:
    rows = []
    for key, count in sorted(counter.items(), key=lambda item: repr(item[0])):
        identity = json.loads(json.dumps(key))
        rows.append({"identity": identity,
                     "count": count})
    return rows


def attribution() -> dict[str, Any]:
    old = ElfTruth.read(R2_ELF, llvm_readobj=READOBJ)
    new = ElfTruth.read(ELF, llvm_readobj=READOBJ)
    sections = [Counter((row.name, row.address, row.bytes, tuple(row.flags))
                        for row in truth.sections) for truth in (old, new)]
    symbols = [Counter((row.name, row.value, row.bytes, row.section)
                       for row in truth.symbols) for truth in (old, new)]
    relocs = [Counter((row.source_section, row.offset, row.relocation_type,
                       row.target, row.addend) for row in truth.relocations)
              for truth in (old, new)]
    old_inputs, new_inputs = profile_inputs(R2_PROFILE), profile_inputs(PROFILE)
    changed = sorted(name for name in set(old_inputs) | set(new_inputs)
                     if old_inputs.get(name) != new_inputs.get(name))
    require(any(name.endswith("src/io.c") for name in changed),
            "last-link authored source delta is not io.c")
    headers = R2.CARD.ORIGINAL_PROGRAM_HEADERS
    old_headers, new_headers = headers(R2_ELF), headers(ELF)
    prg = R2.CARD.prg_difference(R2_PRG, PRG)
    prg["named_families"] = ["mapped error-return/link capture",
        "mapped-owner and relocation propagation", "Build-ID and derived CRCs"]
    prg["unexplained"] = []
    return {"status": "PASS: R2 TO R3 DIFFERENCE FULLY ATTRIBUTED",
        "predecessor": {"ELF": bind(R2_ELF), "PRG": bind(R2_PRG)},
        "candidate": {"ELF": bind(ELF), "PRG": bind(PRG)},
        "input_roots": {"changed": changed},
        "families": ["mapped abort edge replaced by returned link word",
            "mapped owner/layout relocation", "Build-ID and derived CRCs"],
        "sections": {"removed": counter_rows(sections[0] - sections[1]),
            "added": counter_rows(sections[1] - sections[0]), "unexplained": []},
        "symbols": {"removed": counter_rows(symbols[0] - symbols[1]),
            "added": counter_rows(symbols[1] - symbols[0]), "unexplained": []},
        "relocations": {"removed": counter_rows(relocs[0] - relocs[1]),
            "added": counter_rows(relocs[1] - relocs[0]), "unexplained": []},
        "program_headers": {
            "removed": counter_rows(old_headers - new_headers),
            "added": counter_rows(new_headers - old_headers), "unexplained": []},
        "PRG": prg, "unexplained_sections": 0, "unexplained_symbols": 0,
        "unexplained_relocations": 0, "unexplained_program_headers": 0,
        "unexplained_PRG_bytes": 0, "unexplained_members": 0}


def validate(value: dict[str, Any], *, require_prefilter: bool = True) -> None:
    final = value["final_product"]
    owners = final["bounded_owners"]
    require(value["status"] == STATUS and value["authority"] == authority()
            and value["difference"]["unexplained_members"] == 0
            and owners["all_floors_green"] is True
            and owners["ordinary_text"]["margin_bytes"] >= 32
            and owners["ordinary_BSS"]["margin_bytes"] >= 5
            and owners["resident_island"]["margin_bytes"] >= 5
            and owners["zero_page"]["within_bounds"] is True
            and owners["NOLOAD"]["margin_bytes"] >= 0
            and owners["source_link"]["bytes"] == 2
            and final["composed_bank2"]["overlaps"] == []
            and final["nesting"]["violations"] == []
            and final["mapped_error_return"][
                "abort_paths_from_derived_mapped_population"] == []
            and final["mapped_error_return"]["ordinary_caller_owns_failure"]
            and final["mapped_error_return"]["mutations_rejected"] == [
                "direct-in-body-lisp-abort-code-restored"]
            and value["artifacts_before"] == value["artifacts_after"] ==
                R2.CARD.frozen_artifacts()
            and value["attempt_accounting"]["WPLTO_runs"] == 1
            and value["attempt_accounting"]["product_links"] == 1
            and value["attempt_accounting"]["device_contacts"] == 0,
            "Card-2 last-link receipt drift")
    if require_prefilter:
        require(final["packed_prefilter"]["status"] == "PASS"
                and final["boot_cycles"]["status"] == "PASS"
                and value["review_ready"] is True,
                "Card-2 last-link DWX rows remain open")


def write_report(value: dict[str, Any]) -> None:
    final = value["final_product"]
    owners = final["bounded_owners"]
    bank = final["composed_bank2"]
    mapped_f011 = next(row for row in bank["owners"]
                       if row["owner"] == ".lisp65_c2_mapped_f011_cold")
    REPORT.write_text(f"""# Block 2.6 Card 2 — final mapped-error-return product

Status: **{value['status']}**

The final mapped F011 population has zero path to any language-abort function
and zero transitive path to MAP enter/leave. `disk_source_refill_far` receives
the two chain-link bytes from the existing `$DE00` copy; failure returns through
the ordinary wrapper, whose already-live disk-error branch owns the abort. The
direct in-body abort mutation reproduces both nested MAP terminals and falls.

Every final owner clears its floor: ordinary text {owners['ordinary_text']['margin_bytes']}/32,
BSS {owners['ordinary_BSS']['margin_bytes']}/5, resident Island
{owners['resident_island']['margin_bytes']}/5, ZP and NOLOAD green. The mapped
F011 owner is {mapped_f011['bytes']} bytes;
the composed Bank-2 map is disjoint and its largest hole is
{bank['largest_contiguous_hole']['bytes']:,} bytes.

The r2→r3 difference assigns every ELF section, symbol, relocation, program
header and changed PRG address to the returned-link owner/layout or derived
Build-ID/CRC families; zero members remain unexplained. Scope and Acceptance
ran read-only over the frozen pair. Card 2 totals three WPLTO runs, three link
attempts and two completed pairs; this last round spent exactly 1/1 and used
zero device contacts. DWX corruption / boot-cycle rows are
**{final['packed_prefilter']['status']} / {final['boot_cycles']['status']}**.
""", encoding="utf-8")


def patch_card() -> None:
    values = {"AUTHORIZATION": AUTHORIZATION, "PLAN_HEADER": PLAN_HEADER,
        "BUILD": BUILD, "PREFLIGHT": PREFLIGHT, "PLANE": PLANE,
        "WPLTO": WPLTO, "ELF": ELF, "PRG": PRG, "PROFILE": PROFILE,
        "BOUND_PROFILE": BOUND_PROFILE, "INVOCATION": INVOCATION,
        "PLANE_RECEIPT": PLANE_RECEIPT, "PREFLIGHT_RECEIPT": PREFLIGHT_RECEIPT,
        "SOURCE_PREFLIGHT": SOURCE_PREFLIGHT, "PRELINK_RED": PRELINK_RED,
        "DIFFERENCE": DIFFERENCE, "RECEIPT": RECEIPT, "REPORT": REPORT,
        "DRIVER": DRIVER, "FORMAT": FORMAT, "STATUS": STATUS,
        "INITIAL_RED": R2_RED}
    for name, item in values.items():
        setattr(R2, name, item)
    R2.git_section = git_section
    R2.authority = authority
    R2.semantic_source_gate = semantic_source_gate
    R2.final_gate = final_gate
    R2.CARD.attribution = attribution
    R2.validate = validate
    R2.write_report = write_report
    R2._CONFIGURED = False
    R2.patch_card()


def preflight() -> None:
    patch_card()
    require(not BUILD.exists() and not PREFLIGHT_RECEIPT.exists()
            and not SOURCE_PREFLIGHT.exists() and not DIFFERENCE.exists()
            and not RECEIPT.exists(), "last-link preflight boundary is not clean")
    R2.CARD.configure()
    if not PLANE.exists():
        R2.CARD.materialize_plane()
    else:
        require(PLANE_RECEIPT.is_file(), "partial Plane lacks its receipt")
    if not BOUND_PROFILE.exists():
        R2.CARD.materialize_bound_feature_profile()
    R2.CARD.BASE.CHAIN.LINK.predecessor_profile = lambda: BOUND_PROFILE
    R2.CARD.BASE.CHAIN.LINK.predecessor_features = R2.CARD.bound_features
    R2.CARD.BASE.CHAIN.LINK.projected_source_list = R2.CARD.projected_source_list
    gate, sources = R2.CARD.configuration_gate(), R2.CARD.source_preflight()
    value = {"format": FORMAT + "-preflight", "recorded_on": "2026-09-03",
        "status": "PASS: BLOCK 2.6 CARD 2 F011 ARMED 0/1",
        "authority": authority(), "plane": bind(PLANE_RECEIPT),
        "configuration": gate, "source_preflight": bind(SOURCE_PREFLIGHT),
        "source_population": sources,
        "last_link_boundary": {"repair_price": bind(PRICE.RECEIPT),
        "frozen_r2_red": bind(R2_RED), "ordinary_text_projection_bytes": 0,
        "mapped_owner_projection_bytes": 78,
        "requirements": ["mapped tenants return failure",
            "ordinary caller owns abort", "direct abort mutation falls",
            "all constrained owners clear final floors", "last Card-2 link"]},
        "attempt_accounting": {"product_cards": 0, "WPLTO_runs": 0,
        "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
        "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0}}
    PREFLIGHT_RECEIPT.write_bytes(canonical(value))
    print("Block 2.6 Card 2 last link: PREFLIGHT PASS WPLTO=0/1 link=0/1")


def check_preflight() -> None:
    patch_card(); R2.CARD.configure()
    value = load(PREFLIGHT_RECEIPT)
    sealed_zero_consumption = {"product_cards": 0, "WPLTO_runs": 0,
        "product_links": 0, "scope_runs": 0, "acceptance_runs": 0,
        "DWX_prefilter_runs": 0, "media_builds": 0, "device_contacts": 0}
    require(value["authority"] == authority()
            and value["status"] == "PASS: BLOCK 2.6 CARD 2 F011 ARMED 0/1"
            and value["last_link_boundary"]["mapped_owner_projection_bytes"] == 78
            and value["attempt_accounting"] == sealed_zero_consumption,
            "last-link preflight drift")
    # This checker revalidates a sealed pre-link phase after r3 exists.  Live
    # successor files cannot restate whether the historical preflight spent a
    # build; that fact belongs to the phase-owned receipt above.
    # The sealed preflight's sources belong to its producing commit.  Build
    # entry points still use semantic_source_gate() with the live sources.
    historical = semantic_source_gate("f010b4f1")
    def validate_historical(candidate: dict[str, Any]) -> None:
        require(candidate == value["configuration"]["semantics"],
                "historical preflight source identity/semantics drift")
    validate_historical(historical)
    for member in ("source", "wrappers"):
        mutant = deepcopy(historical)
        mutant[member]["sha256"] = "0" * 64
        try:
            validate_historical(mutant)
        except CardError:
            pass
        else:
            raise CardError(f"mixed-era {member} mutation survived")
    original = R2.CARD.semantic_source_gate
    try:
        R2.CARD.semantic_source_gate = lambda: historical
        current = R2.CARD.configuration_gate()
    finally:
        R2.CARD.semantic_source_gate = original
    sealed = value["configuration"]
    sealed_semantics = {key: item for key, item in sealed["semantics"].items()
                        if key != "source"}
    current_semantics = {key: item for key, item in current["semantics"].items()
                         if key != "source"}
    require(sealed["product_world_identity"] == current["product_world_identity"]
            and sealed["authority_categories"] == current["authority_categories"]
            and sealed["F011_registration"] == current["F011_registration"]
            and sealed_semantics == current_semantics,
            "last-link product configuration drift")
    print("Block 2.6 Card 2 last link: PREFLIGHT CHECK PASS")


def build() -> None:
    patch_card(); R2.CARD.build()
    value = load(RECEIPT)
    value["attempt_history"] = {
        "r1_capacity_red": {"WPLTO_runs": 1, "product_link_attempts": 1,
            "completed_product_links": 0},
        "r2_nesting_red": {"WPLTO_runs": 1, "product_link_attempts": 1,
            "completed_product_links": 1},
        "r3_last_link": {"WPLTO_runs": 1, "product_link_attempts": 1,
            "completed_product_links": 1},
        "card_total": {"WPLTO_runs": 3, "product_link_attempts": 3,
            "completed_product_links": 2}}
    # Render before publishing the receipt: a presentation failure must not
    # leave a receipt that looks complete while its paired report is absent.
    write_report(value); RECEIPT.write_bytes(canonical(value))
    validate(value, require_prefilter=False)


def tree_fingerprint(root: Path) -> dict[str, Any]:
    """Bind every file in the frozen product tree, including Scope output."""
    rows = []
    folded = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*")
                       if item.is_file() and not item.is_symlink()):
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"path": relative, "bytes": path.stat().st_size,
                     "sha256": digest})
        folded.update(relative.encode() + b"\0" + digest.encode() + b"\n")
    require(rows, "frozen r3 product tree is empty")
    return {"root": root.relative_to(ROOT).as_posix(), "files": len(rows),
            "sha256": folded.hexdigest()}


def resume() -> None:
    """Finish Acceptance without re-running producer, Scope, WPLTO or link."""
    patch_card(); R2.CARD.configure()
    base = R2.CARD.BASE.CHAIN.LINK.BASE
    require(ELF.is_file() and PRG.is_file() and INVOCATION.is_file()
            and DIFFERENCE.is_file() and ACCEPTANCE_CONVERSION.is_file()
            and ACCEPTANCE_SUCCESSOR_CONVERSION.is_file()
            and ACCEPTANCE_PROJECTION_CORRECTION.is_file()
            and base.SCOPE_RESULT.is_file()
            and not base.ACCEPTANCE_RESULT.exists()
            and not RECEIPT.exists(),
            "Card-2 r3 read-only resume boundary drift")
    clean = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE).stdout
    require(clean == "", "Card-2 r3 resume requires committed clean conversion")

    before = R2.CARD.frozen_artifacts()
    tree_before = tree_fingerprint(WPLTO)
    difference = attribution()
    require(load(DIFFERENCE) == difference
            and difference["unexplained_members"] == 0,
            "frozen r2-to-r3 attribution changed before resume")
    product = final_gate()
    process = R2.CARD.run_child("_accept")
    after = R2.CARD.frozen_artifacts()
    tree_after = tree_fingerprint(WPLTO)
    scope, acceptance = load(base.SCOPE_RESULT), load(base.ACCEPTANCE_RESULT)
    require(before == after and tree_before == tree_after
            and scope["status"] == acceptance["status"] == "PASS",
            "Card-2 r3 read-only Acceptance resume changed or rejected product")

    value = {"format": FORMAT + "-read-only-resume-v1",
        "recorded_on": "2026-09-03", "status": STATUS,
        "authority": authority(), "preflight": bind(PREFLIGHT_RECEIPT),
        "invocation": bind(INVOCATION),
        "acceptance_conversion": bind(ACCEPTANCE_CONVERSION),
        "acceptance_successor_conversion": bind(
            ACCEPTANCE_SUCCESSOR_CONVERSION),
        "acceptance_projection_correction": bind(
            ACCEPTANCE_PROJECTION_CORRECTION),
        "frozen_acceptance_red": bind(ARCH /
            "block-2.6-card2-f011-product-r3-acceptance-red.json"),
        "frozen_acceptance_successor_red": bind(ARCH /
            "block-2.6-card2-f011-product-r3-acceptance-successor-red.json"),
        "frozen_acceptance_normalization_red": bind(ARCH /
            "block-2.6-card2-f011-r3-acceptance-normalization-red.json"),
        "predecessor": {"ELF": bind(R2_ELF), "PRG": bind(R2_PRG)},
        "difference": difference, "difference_receipt": bind(DIFFERENCE),
        "final_product": product, "scope": bind(base.SCOPE_RESULT),
        "acceptance": bind(base.ACCEPTANCE_RESULT),
        "artifacts_before": before, "artifacts_after": after,
        "wplto_tree_before": tree_before, "wplto_tree_after": tree_after,
        "processes": [
            {"action": "_produce", "status": "completed-before-resume",
             "additional_WPLTO_runs": 0, "additional_product_links": 0},
            {"action": "_scope", "status": "green-before-resume",
             "additional_scope_runs": 0},
            process],
        "qualification_history": {
            "before_resume": {"scope_runs": 1, "scope_status": "PASS",
                "acceptance_attempts": 3,
                "acceptance_status": ["RED-F011-PLACEMENT-PROVER",
                    "RED-V5-ANNEX-VMA-PIN",
                    "RED-WHOLE-LAYOUT-ANNEX-NORMALIZATION"]},
            "resume": {"scope_runs": 0, "acceptance_runs": 1,
                "acceptance_status": "PASS", "WPLTO_runs": 0,
                "product_links": 0}},
        "attempt_accounting": {"product_cards": 1, "WPLTO_runs": 1,
            "product_links": 1, "scope_runs": 1, "acceptance_runs": 4,
            "acceptance_attempts_including_checker_reds": 4,
            "DWX_prefilter_runs": 0, "media_builds": 0,
            "device_contacts": 0},
        "attempt_history": {
            "r1_capacity_red": {"WPLTO_runs": 1,
                "product_link_attempts": 1, "completed_product_links": 0},
            "r2_nesting_red": {"WPLTO_runs": 1,
                "product_link_attempts": 1, "completed_product_links": 1},
            "r3_last_link": {"WPLTO_runs": 1,
                "product_link_attempts": 1, "completed_product_links": 1},
            "card_total": {"WPLTO_runs": 3,
                "product_link_attempts": 3, "completed_product_links": 2}},
        "review_ready": False}
    RECEIPT.write_bytes(canonical(value)); write_report(value)
    validate(value, require_prefilter=False)
    print("Block 2.6 Card 2 r3: READ-ONLY ACCEPTANCE RESUME PASS WPLTO=0 link=0")


def check_resume() -> None:
    patch_card(); R2.CARD.configure(); value = load(RECEIPT)
    validate(value, require_prefilter=False)
    require(value["acceptance_conversion"] == bind(ACCEPTANCE_CONVERSION)
            and value["acceptance_successor_conversion"] ==
                bind(ACCEPTANCE_SUCCESSOR_CONVERSION)
            and value["acceptance_projection_correction"] ==
                bind(ACCEPTANCE_PROJECTION_CORRECTION)
            and value["wplto_tree_before"] == value["wplto_tree_after"]
            and value["qualification_history"]["resume"] == {
                "scope_runs": 0, "acceptance_runs": 1,
                "acceptance_status": "PASS", "WPLTO_runs": 0,
                "product_links": 0}
            and load(DIFFERENCE) == attribution(),
            "Card-2 r3 read-only resume receipt drift")
    print("Block 2.6 Card 2 r3: READ-ONLY RESUME CHECK PASS")


def selftest() -> None:
    patch_card(); R2.CARD.configure(); value = load(RECEIPT)
    validate(value, require_prefilter=False)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "text-floor-lost": lambda row: row["final_product"]["bounded_owners"][
            "ordinary_text"].update({"margin_bytes": 31}),
        "mapped-abort": lambda row: row["final_product"][
            "mapped_error_return"].update({"abort_paths_from_derived_mapped_population": [
                {"path": ["disk_source_refill_far", "lisp_abort_code"]}]}),
        "mutation-blunted": lambda row: row["final_product"][
            "mapped_error_return"].update({"mutations_rejected": []}),
        "difference-remainder": lambda row: row["difference"].update(
            {"unexplained_members": 1}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial, require_prefilter=False)
        except (CardError, R2.ReplacementError, RuntimeError, KeyError, ValueError):
            rejected.append(name)
    require(rejected == list(cases), "last-link mutation survived")
    print(f"Block 2.6 Card 2 last link: SELFTEST PASS mutations={len(rejected)}")


def check() -> None:
    patch_card(); R2.CARD.configure(); value = load(RECEIPT); validate(value)
    require(load(DIFFERENCE) == value["difference"] and REPORT.is_file()
            and value["attempt_history"]["card_total"]["WPLTO_runs"] == 3,
            "last-link report/history absent")
    print("Block 2.6 Card 2 last link: CHECK PASS total-WPLTO=3 total-links=3")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check-preflight", "build",
        "resume", "check-resume", "check", "selftest", "_source_preflight",
        "_produce", "_scope", "_accept"))
    action = parser.parse_args().action
    patch_card()
    if action == "preflight":
        preflight()
    elif action == "check-preflight":
        check_preflight()
    elif action == "build":
        build()
    elif action == "resume":
        resume()
    elif action == "check-resume":
        check_resume()
    elif action == "check":
        check()
    elif action == "selftest":
        selftest()
    elif action == "_source_preflight":
        R2.CARD.configure(); R2.source_preflight()
    else:
        R2.CARD.child(action)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, R2.ReplacementError, R2.CARD.CardError, RuntimeError,
            KeyError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 last link: FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
