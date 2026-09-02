#!/usr/bin/env python3
"""Price the sealed Block-3 freight on the living v2.0 product world."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_substitution_artifacts as SUB  # noqa: E402
import c2_v17_ide_idle_blink_card as CARD3  # noqa: E402
import c2_v17_repl_idle_blink_card as CARD2  # noqa: E402
import c2_v17_sexp_scanner_paint_card as CARD1  # noqa: E402
import c2_v200_comfort_return_card as COMFORT  # noqa: E402
import evidence_era as ERA  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v2.0.0-pre-plan.md"
AUTHORIZATION = "9cb99bca"
PLAN_HEADER = "## Owner decision — Comfort leads v2.1 — 2026-08-31"
BUILD = ROOT / "build/c2.3/v2.0-block3-return-pricing"
STDLIB_SUITE = BUILD / "v2.0-block3-stdlib-suite.json"
IDE_SUITE = BUILD / "v2.0-block3-ide-suite.json"
CURRENT_STDLIB_SUITE = ROOT / (
    "build/c2.3/v1.9.0-release-card-r1-preflight/"
    "native-client-product-stdlib-suite.json")
CURRENT_IDE_SUITE = ROOT / (
    "build/release-v1.5.0/public-product-build/build/c2.3/"
    "v1.5.0-public-selected/ide-codemod/suites/p0-ide-core-lib.json")
HISTORICAL_IDE_SUITE = ROOT / "build/bytecode/dialect-v2/suites/p0-ide-core-lib.json"
CURRENT_PRODUCT = ROOT / (
    "build/c2.3/v2.0-symbol22-first-fault-product-card-r2/"
    "static-plane/narrow-static/product/substitution-artifacts.json")
CURRENT_ELF = ROOT / (
    "build/c2.3/v2.0-symbol22-first-fault-product-card-r2/completion-r4/"
    "lisp65-c2-substitution-linked.prg.elf")
CURRENT_RECEIPT = ARCH / (
    "c2.3-v2.0-symbol22-first-fault-product-card-r4-receipt.json")
HISTORICAL_R10 = ARCH / (
    "c2.3-v1.7-ide-idle-blink-product-card-r10-receipt.json")
COMFORT_MANIFEST = ROOT / (
    "build/c2.3/v2.0-block3-return-pricing/comfort-positive/"
    "repl-comfort.manifest.json")
D5 = ARCH / "c2.3-v1.9-r8-release-terminal-d5-receipt.json"
RECEIPT = ARCH / "c2.3-v2.0-block3-return-pricing-receipt.json"
REPORT = ROOT / "docs/planning/v2.0.0-block3-return-pricing-report.md"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"
STATUS = "PASS: V2.0 BLOCK3 RETURN PRICED; ONE PRODUCT CARD REQUIRED"
FORMAT = "lisp65-c2-v200-block3-return-pricing-v1"
SEALED_COMMIT = "d319058b9aa55b9c120414e05073967ab671b60f"
LIVE_EDITOR = ROOT / "lib/stdlib-read-line.lisp"

SCANNER = [
    "%sexp-code", "%sexp-rest", "%sexp-step", "%sexp-scan",
    "%sexp-open", "%sexp-close", "%sexp-match", "%sexp-paint",
]
LINE = [
    "%frame-low", "%cursor-blink", "%rl-start", "%rl-kind", "%rl-scan",
    "%rl-close", "%rl-open", "%rl-idle", "%rl-clear", "%rl-paint",
    "%rl-poll",
]
IDE = list(CARD3.IDE_FUNCTIONS)
INTEGRATION = ["%rl-session"]
BLOCK3_NAMES = [*SCANNER, *LINE, *IDE]
CANDIDATE_NAMES = [*BLOCK3_NAMES, *INTEGRATION]


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def ordered_json(value: Any) -> bytes:
    """Serialize executable suites without reordering semantic map members."""
    return (json.dumps(value, indent=2) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run(command: list[str], label: str) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def authority() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    text = raw.decode()
    require(text.count(PLAN_HEADER) == 1,
            "v2.0 revised-shape authority section drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    section_lower = " ".join(section.lower().split())
    for token in ("block 3", "mandatory transitive closure gate",
                  "first v2.1 card is therefore a media card"):
        require(token in section_lower,
                f"v2.0 Block-3 authority absent: {token}")
    payload = section.encode()
    return {"commit": AUTHORIZATION, "path": relative,
            "section": PLAN_HEADER, "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "right": "host-only Block-3 requalification and pricing; no WPLTO/link/media"}


def _replace_source(sources: list[str], basename: str, replacement: str) -> None:
    matches = [index for index, source in enumerate(sources)
               if Path(source).name == basename]
    require(len(matches) == 1, f"source owner not unique: {basename}")
    sources[matches[0]] = replacement


def candidate_stdlib_suite() -> dict[str, Any]:
    value = deepcopy(load(CURRENT_STDLIB_SUITE))
    functions = value.get("functions")
    sources = value.get("sources")
    require(isinstance(functions, list) and isinstance(sources, list)
            and not (set(CANDIDATE_NAMES) & set(functions)),
            "living stdlib suite already carries Block-3 freight")
    scanner_at = functions.index("lcc-run")
    functions[scanner_at:scanner_at] = SCANNER
    line_at = functions.index("%rl-render")
    functions[line_at:line_at] = LINE
    functions.insert(functions.index("read-line"), "%rl-session")
    _replace_source(sources, "stdlib-read-line.lisp",
        "lib/stdlib-read-line.lisp")
    load_at = next(index for index, source in enumerate(sources)
                   if Path(source).name == "stdlib-load.lisp")
    sources.insert(load_at, "lib/sexp-depth.lisp")
    omitted = value.setdefault("allow_omitted_defuns", [])
    require(isinstance(omitted, list), "stdlib omission inventory drift")
    omitted.append({"name": "%ide-line-net-depth",
        "reason": ("IDE-only indentation helper; the resident product owns "
                   "only the shared matcher objects from lib/sexp-depth.lisp")})
    require(len(functions) == len(set(functions))
            and set(SCANNER + LINE + INTEGRATION) <= set(functions),
            "Block-3 stdlib function population drift")
    return value


def candidate_ide_suite() -> dict[str, Any]:
    historical = load(HISTORICAL_IDE_SUITE)
    predecessor = load(CURRENT_IDE_SUITE)
    require(set(historical["functions"]) - set(predecessor["functions"]) == set(IDE)
            and not (set(IDE) & set(predecessor["functions"])),
            "historical IDE successor population drift")
    return deepcopy(historical)


def emit(prefix: Path, suite: Path, role: str) -> None:
    command = [sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py",
               "--check", "--emit-artifacts", prefix.relative_to(ROOT).as_posix()]
    if role == "disk-lib":
        command += ["--artifact-role", role, "--base-addr", "0x000000"]
    command.append(suite.relative_to(ROOT).as_posix())
    run(command, f"emit {prefix.name}")


def current_specs() -> list[tuple[str, str, Path]]:
    product = load(CURRENT_PRODUCT)
    rows = product.get("manifests")
    require(isinstance(rows, list) and len(rows) == 6,
            "current six-role product manifest drift")
    result = []
    for key, role, row in zip(
            ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc"),
            ("stdlib", "ide", "idex", "m65d", "buffer", "lcc"), rows):
        path = ROOT / row["path"]
        require(bind(path) == row, f"current product manifest drift: {key}")
        result.append((key, role, path))
    return result


def emit_candidate() -> tuple[dict[str, Any], tuple[tuple[str, str, Path], ...]]:
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    run(["make", "v2-workbench-codemod"], "current v2 Workbench codemod")
    STDLIB_SUITE.write_bytes(ordered_json(candidate_stdlib_suite()))
    IDE_SUITE.write_bytes(ordered_json(candidate_ide_suite()))
    emit(BUILD / "stdlib-p0", STDLIB_SUITE, "stdlib")
    emit(BUILD / "ide", IDE_SUITE, "disk-lib")
    predecessor = current_specs()
    specs = (
        ("stdlib-p0", "stdlib", BUILD / "stdlib-p0.manifest.json"),
        ("ide", "ide", BUILD / "ide.manifest.json"),
        *predecessor[2:],
    )
    old_sub = SUB.BUILD, SUB.SPECS
    old_v6 = V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS
    try:
        SUB.BUILD = BUILD / "product"
        SUB.SPECS = specs
        product = SUB.build()
        total = sum(int(load(path)["code_bytes"])
                    for _key, _role, path in specs)
        V6.OUT = BUILD / "v6-semantics"
        V6.PRODUCT_IDENTITY = BUILD / "product/substitution-artifacts.json"
        V6.STATIC_CODE_BYTES = total
        V6.A.SPECS = specs
        V6.OUT.mkdir(parents=True)
        semantics = V6.host_semantics()
    finally:
        SUB.BUILD, SUB.SPECS = old_sub
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old_v6
    require(semantics["static_bank2"]["code_bytes"] == total,
            "candidate static-plane extent drift")
    return product, specs


def _entry_sizes(manifest: Path, names: list[str]) -> dict[str, int]:
    entries = load(manifest)["entries"]
    rows = {row["name"]: int(row["length"]) for row in entries
            if isinstance(row, dict) and row.get("kind") == "function"
            and isinstance(row.get("name"), str)}
    missing = sorted(set(names) - set(rows))
    require(not missing, f"Block-3 emitted objects absent: {missing}")
    return {name: rows[name] for name in names}


def card3_successor_requalification() -> dict[str, Any]:
    """Apply the sealed Card-3 properties through the A+B session split."""
    ide_source = CARD3.SOURCE.read_text(encoding="utf-8")
    timer_source = CARD3.TIMER.read_text(encoding="utf-8")
    timer_calls = CARD3.calls_by_function(timer_source)
    session_owners = sorted(name for name, calls in timer_calls.items()
        if "%read-line-loop" in calls and "%frame-low" in calls)
    require(session_owners == ["%rl-session"]
            and timer_calls.get("read-line", []).count("%rl-session") == 1
            and "%frame-low" not in timer_calls.get("read-line", []),
            f"A+B line-session ownership drift: {session_owners}")

    # The sealed Card-3 checker names the unsplit owner `read-line`.  Adapt only
    # that evidence-era identity; its structural checks and mutations then run
    # unchanged against the successor owner.
    normalized = timer_source.replace(
        "(defun read-line (&rest prompt)",
        "(defun %armed-read-line (&rest prompt)", 1).replace(
        "(defun %rl-session (native)", "(defun read-line (native)", 1)
    require(normalized != timer_source, "Card-3 session adapter was inert")
    ownership = CARD3.validate_source(ide_source, normalized)
    emitted = CARD3.compile_objects()
    require(emitted["card3_total_bytes"] == 2206
            and emitted["maximum_object_bytes"] == 252
            and emitted["frame_low_bytes"] == 19
            and emitted["current_cursor_blink_bytes"] == 180,
            f"Card-3 successor emission drift: {emitted}")
    mutation_rows = CARD3.mutations(ide_source, normalized)
    require(all(row["caught"] for row in mutation_rows),
            "Card-3 successor mutation escaped")
    observations = CARD3.trace_observations()
    return {"status": "PASS: SEALED CARD 3 ADAPTED TO A+B SESSION OWNER",
        "session_owner": "%rl-session", "wrapper_owner": "read-line",
        "ownership": ownership, "emission": emitted,
        "composed_framebuffer": observations,
        "mutations": mutation_rows}


def host_requalification() -> dict[str, Any]:
    card1 = CARD1.check_live_successor()
    _sealed2, card2 = CARD2.check_sealed_successor()
    card3 = card3_successor_requalification()
    return {"status": "PASS: THREE SEALED CARDS REQUALIFIED ON LIVE SOURCES",
        "card1_external_edges": len(card1["caller_audit"]["external_calls"]),
        "card1_mutations": len(card1["mutations"]),
        "card2_cursor_bytes": card2["emission"]["function_bytes"]["%cursor-blink"],
        "card3_total_bytes": card3["emission"]["card3_total_bytes"],
        "card3_mutations": len(card3["mutations"]),
        "maximum_object_bytes": card3["emission"]["maximum_object_bytes"],
        "card3_session_owner": card3["session_owner"],
        "card3_ownership": card3["ownership"],
        "card3_composed_framebuffer": card3["composed_framebuffer"]}


def comfort_positive_control() -> dict[str, Any]:
    # Materialize the sealed Comfort freight against the same living owner
    # directory used by this price.  A stale build-tree manifest would turn
    # the positive control back into an era-crossing fixture.
    profile = COMFORT.DELIVERY.derive_profile(COMFORT.R4_ELF)
    resident, _live = COMFORT.live_resident_spec(write_file=False)
    positive = COMFORT_MANIFEST.parent
    resident_path = positive / "live-resident.json"
    suite_path = positive / "product-profile-suite.json"
    positive.mkdir(parents=True, exist_ok=True)
    resident_path.write_bytes(canonical(resident))
    suite_path.write_bytes(canonical({
        "extends": str(COMFORT.COMFORT_SUITE.resolve()),
        "resident_suites": [str(resident_path.resolve())],
        "delivered_callprims": profile["delivered_ids"],
        "description": ("sealed Comfort freight materialized only as the "
                        "Block-3 closure positive control"),
    }))
    output = positive / "repl-comfort"
    process = subprocess.run([
        sys.executable, "tools/host-lisp/bytecode_p0_stdlib.py", "--check",
        "--artifact-role", "disk-lib", "--emit-artifacts",
        str(output.relative_to(ROOT)), str(suite_path.relative_to(ROOT)),
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    require(process.returncode == 0,
            "Comfort closure positive-control materialization red:\n"
            + process.stdout)
    value = CLOSURE.derive(CURRENT_PRODUCT, [COMFORT_MANIFEST])
    failures = value["failures"]
    require(value["status"] == "FIRST RED" and len(failures) == 1
            and failures[0]["caller"] == "%repl-step"
            and failures[0]["target"] == "%ide-line-net-depth"
            and failures[0]["classification"] == "anonymous-only",
            "closure gate did not reproduce the final Comfort medium defect")
    return {"status": "PASS: KNOWN COMFORT DANGLING CALLEE REJECTED",
            "failure": failures[0], "product": bind(CURRENT_PRODUCT),
            "external_manifest": bind(COMFORT_MANIFEST)}


def d5_projection() -> dict[str, Any]:
    d5 = load(D5)
    # The receipt carries the release-terminal values in its device row.
    rows: list[dict[str, Any]] = []
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("symbol_slots") == 109 and value.get("namepool_bytes") == 1486:
                rows.append(value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(d5)
    require(rows, "v1.9 release-terminal D5 authority absent")
    name_bytes = sum(len(name.encode("ascii")) + 1 for name in CANDIDATE_NAMES)
    result = {"before": {"symbol_slots": 109, "namepool_bytes": 1486},
        "freight": {"symbol_slots": len(CANDIDATE_NAMES),
                    "namepool_bytes": name_bytes},
        "after": {"symbol_slots": 109 - len(CANDIDATE_NAMES),
                  "namepool_bytes": 1486 - name_bytes},
        "minimum": {"symbol_slots": 32, "namepool_bytes": 384}}
    result["margin"] = {name: result["after"][name] - result["minimum"][name]
                        for name in result["after"]}
    require(result["freight"] == {"symbol_slots": 32, "namepool_bytes": 349}
            and min(result["margin"].values()) >= 0,
            "Block-3 D5 capacity arithmetic drift")
    return result


def bank2_geometry(total: int) -> dict[str, Any]:
    truth = ElfTruth.read(CURRENT_ELF, llvm_readobj=READOBJ)
    far = truth.section(".lisp65_c2_mapped_far_service")
    far_lma = truth.symbol("__lisp65_c2_mapped_far_service_load_start").value
    cold = truth.section(".lisp65_c2_mapped_product_cold")
    cold_lma = truth.symbol("__lisp65_c2_mapped_product_cold_load_start").value
    plane_end = 0x20000 + total
    require(far_lma == 0x2F8B2 and cold_lma == 0x2FE8D
            and plane_end <= far_lma,
            "candidate Block-3 plane collides with mapped tenants")
    return {"bank": [0x20000, 0x30000], "static_plane": [0x20000, plane_end],
        "static_plane_bytes": total,
        "mapped_far_service": {"VMA": far.address, "LMA": far_lma,
                               "bytes": far.bytes},
        "mapped_product_cold": {"VMA": cold.address, "LMA": cold_lma,
                                "bytes": cold.bytes},
        "largest_contiguous_hole": {"start": plane_end,
            "end_exclusive": far_lma, "bytes": far_lma - plane_end},
        "placement_policy": "existing page-congruent $28000 MAP placement",
        "overlaps": []}


def build_receipt() -> dict[str, Any]:
    product, specs = emit_candidate()
    product_path = BUILD / "product/substitution-artifacts.json"
    closure = CLOSURE.derive(product_path)
    closure["mutations_rejected"] = CLOSURE.mutation_tests()
    CLOSURE.require_closed(closure)
    stdlib_sizes = _entry_sizes(specs[0][2], SCANNER + LINE + INTEGRATION)
    ide_sizes = _entry_sizes(specs[1][2], IDE)
    current = current_specs()
    current_total = sum(int(load(path)["code_bytes"])
                        for _key, _role, path in current)
    candidate_total = sum(int(load(path)["code_bytes"])
                          for _key, _role, path in specs)
    new_objects = {**stdlib_sizes, **ide_sizes}
    require(set(new_objects) == set(CANDIDATE_NAMES)
            and len(new_objects) == 32
            and sum(new_objects.values()) - (candidate_total - current_total) == 189
            and product == load(product_path),
            "candidate Block-3 freight population drift")
    r10 = load(HISTORICAL_R10)
    current_receipt = load(CURRENT_RECEIPT)
    return {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS, "authority": authority(),
        "predecessors": {"current_v2_0_r4": bind(CURRENT_RECEIPT),
                         "sealed_block3_r10": bind(HISTORICAL_R10),
                         "current_pair": current_receipt["artifacts_after"],
                         "historical_pair": r10["frozen_pair_after"]},
        "host_requalification": host_requalification(),
        "emission": {"current_plane_bytes": current_total,
            "candidate_plane_bytes": candidate_total,
            "delta_bytes": candidate_total - current_total,
            "block3_named_object_bytes": sum(new_objects.values()),
            "replaced_live_object_credit_bytes":
                sum(new_objects.values()) - (candidate_total - current_total),
            "block3_objects": new_objects,
            "integration_helper": "%rl-session",
            "maximum_object_bytes": max(new_objects.values()),
            "candidate_product": bind(product_path),
            "candidate_manifests": [bind(path) for _key, _role, path in specs]},
        "capacity": {"D5_projection": d5_projection(),
                     "composed_bank2": bank2_geometry(candidate_total)},
        "transitive_packed_medium_closure": closure,
        "closure_positive_control": comfort_positive_control(),
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "media_builds": 0, "device_contacts": 0},
        "recommended_product_card": {"WPLTO_runs": 1, "product_links": 1,
            "reason": ("the Bank-2 plane extent and product build ID change; "
                       "the linked consumers must bind and emit the successor world"),
            "required_gates": ["full v2.0 r4-to-Block3 difference attribution",
                "both-axis bound-equals-consumed authority inventory",
                "composed Bank-2 ownership and tuple=LOADADDR",
                "three sealed Block-3 host cards on live sources",
                "transitive packed product/media callee closure",
                "Scope and Acceptance read-only on the frozen successor pair"]},
        "claim_limit": ("Host-only Block-3 return pricing and closure-gate "
            "positive control. No WPLTO, product link, medium, device or v2.0 "
            "feature acceptance claim.")}


def report(value: dict[str, Any]) -> str:
    emission = value["emission"]
    d5 = value["capacity"]["D5_projection"]
    bank = value["capacity"]["composed_bank2"]
    closure = value["transitive_packed_medium_closure"]
    return f"""# v2.0 Block 3 return — host pricing

Status: **{value['status']}**

The three reviewed Block-3 cards still pass on the living sources.  Their 31
named objects plus the one A+B integration split emit
{emission['block3_named_object_bytes']:,} bytes; the largest
object is {emission['maximum_object_bytes']} bytes.  The complete current
six-image plane grows from {emission['current_plane_bytes']:,} to
{emission['candidate_plane_bytes']:,} bytes (delta
{emission['delta_bytes']:+,}); the {emission['replaced_live_object_credit_bytes']}
byte difference is the living line-editor family replaced by its composed
successor, not hidden freight.

The existing page-congruent `$28000` MAP placement remains sufficient.  The
candidate plane ends at `${bank['static_plane'][1]:05X}` and leaves a largest
contiguous hole of {bank['largest_contiguous_hole']['bytes']:,} bytes before
the Far Service at `$2F8B2`; there are no overlaps.  D5 projects from
109/1,486 to **{d5['after']['symbol_slots']}/{d5['after']['namepool_bytes']:,}**,
leaving margins {d5['margin']['symbol_slots']}/{d5['margin']['namepool_bytes']:,}
above the 32/384 floor.

The mandatory transitive packed-medium closure gate now exists.  It checks all
{closure['object_count']} candidate packed objects and
{closure['call_site_count']:,} emitted call sites in one product/media owner
world.  The Block-3 candidate is closed.  Its sharp positive control rejects
the sealed Comfort freight, freshly materialized against this living owner
directory, at the exact edge observed on the final Comfort medium:
`%repl-step -> %ide-line-net-depth` is `anonymous-only`, not a published
definition.  Thus the new gate would have stopped that medium before deploy.

Block 3 cannot return artifact-only: its new static-plane extent and product
build ID are compiler-consumed product inputs.  The priced successor is one
product card with **one WPLTO and one product link**, followed by full
difference attribution, Scope/Acceptance and only then media.  This report
spends none of that budget.
"""


def check() -> dict[str, Any]:
    require(RECEIPT.is_file() and REPORT.is_file(), "Block-3 pricing absent")
    # This price witnessed the pre-device source world.  The banner-only
    # repair legitimately advances the live editor, so replaying the old
    # pricing card over that successor would rewrite historical evidence.
    # The successor semantics are owned by the dedicated repair preflight.
    if LIVE_EDITOR.read_bytes() != ERA.era_blob(
            SEALED_COMMIT, LIVE_EDITOR.relative_to(ROOT).as_posix()):
        require(RECEIPT.read_bytes() == ERA.era_blob(
                    SEALED_COMMIT, RECEIPT.relative_to(ROOT).as_posix())
                and REPORT.read_bytes() == ERA.era_blob(
                    SEALED_COMMIT, REPORT.relative_to(ROOT).as_posix()),
                "sealed Block-3 pricing evidence was rewritten")
        value = load(RECEIPT)
        require(value.get("status") == STATUS,
                "sealed Block-3 pricing identity drift")
        return value
    value = build_receipt()
    require(RECEIPT.read_bytes() == canonical(value)
            and REPORT.read_text(encoding="utf-8") == report(value),
            "Block-3 pricing drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check"))
    args = parser.parse_args()
    try:
        if args.action == "write":
            value = build_receipt()
            RECEIPT.parent.mkdir(parents=True, exist_ok=True)
            RECEIPT.write_bytes(canonical(value))
            REPORT.write_text(report(value), encoding="utf-8")
        else:
            value = check()
        emission = value["emission"]
        hole = value["capacity"]["composed_bank2"]["largest_contiguous_hole"]
        print("v2.0 Block3 return pricing: PASS "
              f"plane={emission['candidate_plane_bytes']} "
              f"delta={emission['delta_bytes']:+} hole={hole['bytes']} "
              "WPLTO=0 link=0")
        return 0
    except (PricingError, CLOSURE.ClosureError, RuntimeError) as error:
        print(f"v2.0 Block3 return pricing: FIRST RED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
