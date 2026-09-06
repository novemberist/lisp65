#!/usr/bin/env python3
"""Price Card 2's mapped-error-return repair without WPLTO or product link."""

from __future__ import annotations

import argparse
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

import block_26_f011_text_budget_pricing as BASE  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
RED = ARCH / "block-2.6-card2-f011-product-r2-final-red.json"
RECEIPT = ARCH / "block-2.6-card2-f011-map-abort-repair-pricing.json"
REPORT = ROOT / "docs/planning/2.6-card2-f011-map-abort-repair-pricing-report.md"
BUILD = ROOT / "build/2.6/card2-f011-map-abort-repair-pricing"
AUTHORIZATION = "44d2d3f7"
FORMAT = "lisp65-block-2.6-card2-f011-map-abort-repair-pricing-v1"
STATUS = "PASS: CARD 2 MAPPED ERROR-RETURN FORM PRICED"


class PricingError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PricingError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def authority_source() -> tuple[str, dict[str, Any]]:
    relative = "src/io.c"
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return raw.decode(), {"commit": AUTHORIZATION, "path": relative,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def authority_plan_binding() -> dict[str, Any]:
    relative = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(["git", "show", f"{AUTHORIZATION}:{relative}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    return {"path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def replace_once(source: str, old: str, new: str, label: str) -> str:
    require(source.count(old) == 1, f"{label} source seam drift")
    return source.replace(old, new, 1)


SECTOR_BODY = '''#if defined(__mos__) && defined(LISP65_C2_F011_COLD)
LISP65_C2_MAPPED_F011_COLD_FN
unsigned char io_disk_read_sector_far(unsigned char track, unsigned char sector) {
#else
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
#endif
    unsigned int off, i;
#if defined(__mos__) && defined(LISP65_C2_F011_COLD)
    off = f011_read_at_far(track, sector);
#else
    off = f011_read_at(track, sector);
#endif
    if (off == LISP65_F011_READ_FAILED) return 0;
    for (i = 0; i < 256; i++)
        ext_disk_put((unsigned int)(DISK_EXT_DIR + i), ((volatile unsigned char *)0xDE00)[off + i]);
    lisp65_f011_unmap_buffer();
    return 1;
}'''

REFILL_BODY = '''LISP65_C2_MAPPED_F011_COLD_FN
unsigned char disk_source_refill_far(void) {
    unsigned int link = disk_source_link;
    unsigned char t = DISK_SOURCE_LINK_TRACK(link);
    unsigned char s = DISK_SOURCE_LINK_SECTOR(link);
    unsigned char nt, ns;
    unsigned int count;
    if (!(link & DISK_SOURCE_LINK_VALID) || !t ||
        !io_disk_read_sector_far(t, s)) {
        disk_source_link = 0;
        return 0;
    }
    nt = ext_disk_get(DISK_EXT_DIR); ns = ext_disk_get(DISK_EXT_DIR + 1u);
    count = disk_chain_count(t, s, nt, ns);
    if (count > 254u) {
        disk_source_link = 0;
        return 0;
    }
    disk_source_link = DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u);
    return 1;
}'''


def returned_link_source(source: str) -> str:
    sector = '''#if defined(__mos__) && defined(LISP65_C2_F011_COLD)
static LISP65_C2_MAPPED_F011_COLD_FN
unsigned int io_disk_read_sector_link_far(
    unsigned char track, unsigned char sector
) {
    unsigned int off, i, link;
    off = f011_read_at_far(track, sector);
    if (off == LISP65_F011_READ_FAILED) return LISP65_F011_READ_FAILED;
    link = (unsigned int)((volatile unsigned char *)0xDE00)[off] |
        ((unsigned int)((volatile unsigned char *)0xDE00)[off + 1u] << 8);
    for (i = 0; i < 256; i++)
        ext_disk_put((unsigned int)(DISK_EXT_DIR + i),
                     ((volatile unsigned char *)0xDE00)[off + i]);
    lisp65_f011_unmap_buffer();
    return link;
}

LISP65_C2_MAPPED_F011_COLD_FN
unsigned char io_disk_read_sector_far(unsigned char track, unsigned char sector) {
    return (unsigned char)(io_disk_read_sector_link_far(track, sector) !=
                           LISP65_F011_READ_FAILED);
}
#else
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
    unsigned int off, i;
    off = f011_read_at(track, sector);
    if (off == LISP65_F011_READ_FAILED) return 0;
    for (i = 0; i < 256; i++)
        ext_disk_put((unsigned int)(DISK_EXT_DIR + i),
                     ((volatile unsigned char *)0xDE00)[off + i]);
    lisp65_f011_unmap_buffer();
    return 1;
}
#endif'''
    refill = '''LISP65_C2_MAPPED_F011_COLD_FN
unsigned char disk_source_refill_far(void) {
    unsigned int link = disk_source_link;
    unsigned char t = DISK_SOURCE_LINK_TRACK(link);
    unsigned char s = DISK_SOURCE_LINK_SECTOR(link);
    unsigned char nt, ns;
    unsigned int count, read_link;
    if (!(link & DISK_SOURCE_LINK_VALID) || !t) {
        disk_source_link = 0;
        return 0;
    }
    read_link = io_disk_read_sector_link_far(t, s);
    if (read_link == LISP65_F011_READ_FAILED) {
        disk_source_link = 0;
        return 0;
    }
    nt = (unsigned char)read_link;
    ns = (unsigned char)(read_link >> 8);
    count = disk_chain_count(t, s, nt, ns);
    if (count > 254u) {
        disk_source_link = 0;
        return 0;
    }
    disk_source_link = DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u);
    return 1;
}'''
    source = replace_once(source, SECTOR_BODY, sector, "returned-link sector")
    return replace_once(source, REFILL_BODY, refill, "returned-link refill")


def out_parameter_source(source: str) -> str:
    sector = '''#if defined(__mos__) && defined(LISP65_C2_F011_COLD)
static LISP65_C2_MAPPED_F011_COLD_FN
unsigned char io_disk_read_sector_capture_far(
    unsigned char track, unsigned char sector,
    unsigned char *next_track, unsigned char *next_sector
) {
    unsigned int off, i;
    off = f011_read_at_far(track, sector);
    if (off == LISP65_F011_READ_FAILED) return 0;
    if (next_track) {
        *next_track = ((volatile unsigned char *)0xDE00)[off];
        *next_sector = ((volatile unsigned char *)0xDE00)[off + 1u];
    }
    for (i = 0; i < 256; i++)
        ext_disk_put((unsigned int)(DISK_EXT_DIR + i),
                     ((volatile unsigned char *)0xDE00)[off + i]);
    lisp65_f011_unmap_buffer();
    return 1;
}

LISP65_C2_MAPPED_F011_COLD_FN
unsigned char io_disk_read_sector_far(unsigned char track, unsigned char sector) {
    return io_disk_read_sector_capture_far(track, sector, 0, 0);
}
#else
unsigned char io_disk_read_sector(unsigned char track, unsigned char sector) {
    unsigned int off, i;
    off = f011_read_at(track, sector);
    if (off == LISP65_F011_READ_FAILED) return 0;
    for (i = 0; i < 256; i++)
        ext_disk_put((unsigned int)(DISK_EXT_DIR + i),
                     ((volatile unsigned char *)0xDE00)[off + i]);
    lisp65_f011_unmap_buffer();
    return 1;
}
#endif'''
    refill = '''LISP65_C2_MAPPED_F011_COLD_FN
unsigned char disk_source_refill_far(void) {
    unsigned int link = disk_source_link;
    unsigned char t = DISK_SOURCE_LINK_TRACK(link);
    unsigned char s = DISK_SOURCE_LINK_SECTOR(link);
    unsigned char nt, ns;
    unsigned int count;
    if (!(link & DISK_SOURCE_LINK_VALID) || !t ||
        !io_disk_read_sector_capture_far(t, s, &nt, &ns)) {
        disk_source_link = 0;
        return 0;
    }
    count = disk_chain_count(t, s, nt, ns);
    if (count > 254u) {
        disk_source_link = 0;
        return 0;
    }
    disk_source_link = DISK_SOURCE_LINK_PACK(nt, nt ? ns : 0u);
    return 1;
}'''
    source = replace_once(source, SECTOR_BODY, sector, "out-parameter sector")
    return replace_once(source, REFILL_BODY, refill, "out-parameter refill")


def mapped_body(source: str, name: str) -> str:
    start = source.index(f"{name}(")
    start = source.index("{", start)
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise PricingError(f"unterminated body: {name}")


def source_contract(source: str) -> dict[str, Any]:
    refill = mapped_body(source, "disk_source_refill_far")
    sector = mapped_body(source, "io_disk_read_sector_link_far")
    checks = {
        "mapped-refill-has-no-aborting-read": "ext_disk_get" not in refill,
        "mapped-refill-has-no-abort-site": "lisp_abort" not in refill,
        "mapped-sector-has-no-abort-site": "lisp_abort" not in sector,
        "link-captured-before-unmap": (
            "((volatile unsigned char *)0xDE00)[off]" in sector and
            sector.index("((volatile unsigned char *)0xDE00)[off]") <
            sector.index("lisp65_f011_unmap_buffer()")),
        "failure-is-returned": sector.count(
            "return LISP65_F011_READ_FAILED;") == 1,
        "ordinary-public-contract-preserved": (
            "unsigned char io_disk_read_sector_far" in source and
            "!=\n                           LISP65_F011_READ_FAILED" in source),
        "ordinary-refill-wrapper-retained": source.count(
            "unsigned char disk_source_refill(void);") == 1,
    }
    require(all(checks.values()), "mapped error-return source contract failed")
    mutant = source.replace(
        "nt = (unsigned char)read_link;",
        "nt = ext_disk_get(DISK_EXT_DIR);", 1)
    require("ext_disk_get" in mapped_body(mutant, "disk_source_refill_far"),
            "direct abort-capable read mutation did not arm")
    return {"checks": checks,
        "mapped_failure_protocol": "return status/link word; ordinary caller raises",
        "mutations_rejected": ["direct-in-body-ext-disk-get-restored"]}


def delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {key: after[key] - before[key] for key in sorted(before)}


def measured_lane(name: str, source: str, flags: list[str]) -> dict[str, Any]:
    """Create a lane once, then re-derive its receipt from immutable outputs."""
    directory = BUILD / name
    if not directory.exists():
        return BASE.lane(name, source, flags, BASE.MAPPED_COLD_WRAPPERS)
    source_path = directory / "io.c"
    bitcode = directory / "io.c.o"
    combined = directory / "combined-c.bc"
    obj = directory / "combined-c.o"
    require(source_path.read_text(encoding="utf-8") == source,
            f"{name} cached source drift")
    return {"source": bind(source_path), "bitcode": bind(bitcode),
        "combined_bitcode": bind(combined), "object": bind(obj),
        "symbols": BASE.symbol_sizes(obj), "sections": BASE.section_sizes(obj)}


def derive() -> dict[str, Any]:
    plan = subprocess.run(["git", "show", f"{AUTHORIZATION}:"
        "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"],
        cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout
    folded = " ".join(plan.lower().replace("`", "").split())
    for token in ("host-only repair pricing round", "mapped body never aborts",
                  "last link"):
        require(token in folded, f"repair-price authority absent: {token}")
    red = load(RED)
    require(red["status"].startswith("FROZEN:")
            and len(red["attribution"]["violations"]) == 2
            and red["qualification"]["scope_runs"] == 0,
            "frozen r2 nesting boundary drift")
    source, source_binding = authority_source()
    variants = {
        "frozen-r2-abort-reachable": source,
        "returned-link-word": returned_link_source(source),
        "out-parameters": out_parameter_source(source),
    }
    BUILD.mkdir(parents=True, exist_ok=True)
    old_build = BASE.BUILD
    BASE.BUILD = BUILD
    try:
        flags = [*BASE.GUARD.compile_flags(), "-DLISP65_C2_F011_COLD"]
        lanes = {name: measured_lane(name, text, flags)
                 for name, text in variants.items()}
    finally:
        BASE.BUILD = old_build
    for row in lanes.values():
        row["groups"] = BASE.group_sections(row["sections"])
    baseline = lanes["frozen-r2-abort-reachable"]["groups"]
    for row in lanes.values():
        row["delta_vs_frozen_r2"] = delta(row["groups"], baseline)
    candidates = {name: row for name, row in lanes.items()
                  if name != "frozen-r2-abort-reachable"}
    eligible = {name: row for name, row in candidates.items()
                if row["delta_vs_frozen_r2"]["ordinary_text_bytes"] <= 0}
    require(eligible, "no repair form protects the zero-slack ordinary-text wall")
    selected = min(eligible, key=lambda name: (
        eligible[name]["groups"]["mapped_f011_cold_bytes"], name))
    require(selected == "returned-link-word",
            f"price did not produce one expected winner: {selected}")
    contract = source_contract(variants[selected])
    return {"format": FORMAT, "recorded_on": "2026-09-03", "status": STATUS,
        "authority": {"commit": AUTHORIZATION, "plan": authority_plan_binding(),
            "frozen_r2_red": bind(RED), "source": source_binding,
            "right": "host-only price then one last replacement WPLTO/link"},
        "measurement": {"kind": "bounded whole-C relocatable codegen",
            "final_link_claim": False, "WPLTO_runs": 0,
            "product_links": 0, "device_contacts": 0, "lanes": lanes},
        "decision": {"selected": selected,
            "eligible_forms": sorted(eligible),
            "selection_rule": "no ordinary-text growth, then smallest mapped owner",
            "ordinary_text_delta_projection": candidates[selected][
                "delta_vs_frozen_r2"]["ordinary_text_bytes"],
            "mapped_owner_delta_projection": candidates[selected][
                "delta_vs_frozen_r2"]["mapped_f011_cold_bytes"],
            "final_link_required": True,
            "reason": "captures link bytes during the existing mapped copy and returns failure"},
        "source_contract": contract,
        "final_link_debts": ["all constrained owners at or above floors",
            "transitive mapped closure has zero MAP transitions",
            "direct in-body abort mutation falls", "corrupt sector fails from ordinary caller",
            "boot cycles remeasured", "full attribution with zero unexplained"],
        "next": "apply selected source form and spend Card 2's last authorized link"}


def report(value: dict[str, Any]) -> str:
    lanes = value["measurement"]["lanes"]
    selected = lanes[value["decision"]["selected"]]["delta_vs_frozen_r2"]
    other = lanes["out-parameters"]["delta_vs_frozen_r2"]
    return f"""# Block 2.6 Card 2 — mapped-abort repair pricing

Status: **{value['status']}**

Three bounded whole-C codegen lanes compare the frozen r2 body with two
error-return forms. They perform **0 WPLTOs, 0 product links and 0 device
contacts** and make no final-capacity claim.

The selected form is **returned link word**. During the existing mapped
`$DE00` copy it captures the two chain-link bytes, returns the word (or the
existing failure sentinel), and leaves all abort decisions to the ordinary
caller. Its projected delta against r2 is {selected['ordinary_text_bytes']:+d}
ordinary-text bytes and {selected['mapped_f011_cold_bytes']:+d} mapped-owner
bytes. The out-parameter alternative projects {other['ordinary_text_bytes']:+d}
ordinary-text and {other['mapped_f011_cold_bytes']:+d} mapped bytes.

The direct `ext_disk_get` edge is absent from the selected mapped refill and
is a falling source mutation when restored. Final-link placement, the full
transitive nesting proof, the ordinary-caller corrupt-sector outcome, boot
cycles and attribution remain debts of the already authorized last link.
"""


def validate(value: dict[str, Any]) -> None:
    current = derive()
    require(value == current and value["status"] == STATUS
            and value["decision"]["selected"] == "returned-link-word"
            and value["decision"]["ordinary_text_delta_projection"] <= 0
            and value["measurement"]["WPLTO_runs"] == 0
            and value["measurement"]["product_links"] == 0
            and value["source_contract"]["checks"][
                "mapped-refill-has-no-aborting-read"],
            "mapped-abort repair price drift")


def write() -> None:
    require(not RECEIPT.exists() and not REPORT.exists() and not BUILD.exists(),
            "mapped-abort pricing is one-shot")
    value = derive()
    RECEIPT.write_bytes(canonical(value))
    REPORT.write_text(report(value), encoding="utf-8")
    validate(value)
    print("Block 2.6 Card 2 MAP-abort price: PASS selected=returned-link-word")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(REPORT.is_file() and REPORT.read_text(encoding="utf-8") == report(value),
            "mapped-abort repair report drift")
    print("Block 2.6 Card 2 MAP-abort price: CHECK PASS")


def selftest() -> None:
    value = load(RECEIPT)
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "ordinary-growth-hidden": lambda row: row["decision"].update(
            {"ordinary_text_delta_projection": 1}),
        "abort-edge-hidden": lambda row: row["source_contract"]["checks"].update(
            {"mapped-refill-has-no-aborting-read": False}),
        "link-spent-in-price": lambda row: row["measurement"].update(
            {"product_links": 1}),
        "wrong-winner": lambda row: row["decision"].update(
            {"selected": "out-parameters"}),
    }
    rejected = []
    for name, mutate in cases.items():
        trial = deepcopy(value); mutate(trial)
        try:
            validate(trial)
        except (PricingError, KeyError, ValueError, RuntimeError):
            rejected.append(name)
    require(rejected == list(cases), "mapped-abort pricing mutation survived")
    print(f"Block 2.6 Card 2 MAP-abort price: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "check", "selftest"))
    action = parser.parse_args().action
    {"write": write, "check": check, "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PricingError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"Block 2.6 Card 2 MAP-abort price: RED {error}", file=sys.stderr)
        raise SystemExit(2)
