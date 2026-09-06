#!/usr/bin/env python3
"""Derive and enforce the Block 2.6 closing report from card evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
RECEIPT = EVIDENCE / "block-2.6-closure-receipt.json"
REPORT = ROOT / "docs/planning/2.6-correctness-and-build-integrity-block-report.md"
DOMAIN = ROOT / "config/public-surface-domain-contract.json"
PARKED = ROOT / "docs/reference/parked-items-register.md"

INPUTS = {
    "card1": EVIDENCE / "block-2.6-card1-sidx-product-r2-receipt.json",
    "card2": EVIDENCE / "block-2.6-card2-f011-product-r3-receipt.json",
    "card3": EVIDENCE / "block-2.6-card3-vm-hardening-product-r2-receipt.json",
    "card3_dwx": EVIDENCE / "block-2.6-card3-vm-hardening-dwx-r2.json",
    "card4": EVIDENCE / "block-2.6-card4-compiler-prelude-receipt.json",
    "card5": EVIDENCE / "block-2.6-card5-build-integrity-receipt.json",
    "card6": EVIDENCE / "block-2.6-card6-small-hardening-dma-tuple-repair-r3-receipt.json",
    "card6_dwx": EVIDENCE / "block-2.6-card6-small-hardening-dma-tuple-repair-dwx-r3.json",
    "domain_contract": DOMAIN,
}


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> dict[str, Any]:
    return {name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in INPUTS.items()}


def nested_values(value: Any, key: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key:
                found.append(child)
            found.extend(nested_values(child, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(nested_values(child, key))
    return found


def validate(data: dict[str, Any], parked: str) -> dict[str, Any]:
    for name in ("card1", "card2", "card3", "card4", "card6"):
        require(str(data[name].get("status", "")).startswith("PASS"),
                f"{name} is not green")
    require(data["card5"].get("status") == "passed", "card5 is not green")
    for name in ("card3_dwx", "card6_dwx"):
        require(str(data[name].get("status", "")).startswith("PASS"),
                f"{name} is not green")

    for name, value in data.items():
        for contacts in nested_values(value, "device_contacts"):
            require(contacts == 0, f"{name} claims a physical-device contact")
        for key in ("unexplained_members", "unexplained_PRG_bytes",
                    "unexplained_sections", "unexplained_symbols",
                    "unexplained_relocations", "unexplained_program_headers"):
            for unexplained in nested_values(value, key):
                require(unexplained in (0, []), f"{name} has {key}={unexplained!r}")

    c1 = data["card1"]
    require(c1["final_product"]["symbol_domain"]["executed_mutation"]["mutation"]
            == "remove sf_setq eval_symbol_arg_p check",
            "card1 sharp symbol-domain mutation is absent")
    require(c1["artifacts_after"]["ELF"]["sha256"].startswith("9a80d985"),
            "card1 final ELF identity changed")

    c2 = data["card2"]
    require(c2["final_product"]["semantics"]["status"]
            == "PASS: MAPPED TENANT RETURNS; ORDINARY CALLER OWNS ERROR",
            "card2 mapped error-return rule is absent")
    require(c2["final_product"]["boot_cycles"]["ratio"] < 1.0,
            "card2 boot-cycle observation regressed")
    require(c2["final_product"]["bounded_owners"]["all_floors_green"],
            "card2 has a bounded owner below its floor")

    c3 = data["card3"]
    gc = c3["final_product"]["gc_cycle_wall"]
    require(gc["status"] == "PASS" and gc["ratio"] < 1.0,
            "card3 GC-cycle wall is not green")
    require(c3["final_product"]["fixed_raw_BSS_layout"]["status"].startswith("PASS"),
            "card3 fixed-raw BSS owners are not linker-visible")
    sharp = set(c3["final_product"]["vm_hardening"]["sharp_mutations"])
    require({"product-root-omitted", "slot-bound-removed",
             "rest-transient-bound-removed",
             "pop-fail-stop-and-disk-domain-removed",
             "disk-poke-domain-removed"} <= sharp,
            "card3 sharp mutation population is incomplete")
    card3_runs = data["card3_dwx"]["gc_cycle_wall"]["candidate_runs"]
    require(card3_runs and all(run["post_input_symbol_oracle"] == 9
                               and run["post_input_length_oracle"] == 7
                               for run in card3_runs),
            "card3 six-line print witness is not green")

    counts = data["domain_contract"]["counts"]
    require(counts == {"error-raised": 546, "documented-permissive": 178,
                       "silently-wrong": 110},
            f"durable domain contract has unexpected counts: {counts!r}")
    require(data["card4"]["domain_contract"]["counts"] == counts,
            "card4 and durable domain contract disagree")
    require(len(data["card4"]["mutations_rejected"]) == 8,
            "card4 mutation population changed")

    c5 = data["card5"]
    require(c5["facts"]["explicit_product_lifecycles"] == 6,
            "card5 explicit lifecycle population changed")
    require(c5["facts"]["toolchain_verified_on_product_path"],
            "card5 product path no longer verifies its toolchain")
    require("changed-source-verifies-old-bytes" in c5["mutation_suite"]["names"],
            "card5 verify-instead-of-build mutation is absent")

    c6 = data["card6"]
    values = c6["final_product"]["small_hardening"]["descriptor_emission"]["executed_values"]
    require(values["final_trigger_population"] == 9,
            "card6 descriptor user population is not nine")
    require(values["packed_slice"]["encoded_source_tuple"] == 0x8200,
            "card6 packed EDMA source tuple is not $8200")
    require("byte-2-20-ordinary-u32-recomposition" in values["mutations_rejected"],
            "card6 byte-2 $20 mutation is absent")
    owners = c6["final_product"]["bounded_owners"]
    require(owners["all_floors_green"], "card6 has a bounded owner below its floor")
    watch = c6["final_product"]["e000_capture_watch"]
    require(watch["free_bytes"] == 67 and watch["floor_bytes"] == 54,
            "card6 E000 floor changed")
    require(watch["capture_watch_bytes"] == watch["capture_watch_floor_bytes"] == 57,
            "card6 capture watch is not exactly at its floor")
    require(c6["final_product"]["boot_cycles"]["ratio"] < 1.0,
            "card6 boot-cycle observation regressed")
    require(data["card6_dwx"]["forced_collection_and_print9"]["status"] == "PASS",
            "card6 six-line print witness is not green")

    require("A7 — `pc < payload_len` before fetch" in parked,
            "A7 restart package is absent from the parked register")
    require("A15 string-builder latch" in parked,
            "A15 restart package is absent from the parked register")

    return {
        "cards_green": 6,
        "device_contacts": 0,
        "domain_contract": counts,
        "card1": {
            "ELF": c1["artifacts_after"]["ELF"]["sha256"],
            "PRG": c1["artifacts_after"]["PRG"]["sha256"],
            "symbol_domain_mutation": c1["final_product"]["symbol_domain"]["executed_mutation"]["mutation"],
        },
        "card2": {
            "ELF": c2["artifacts_after"]["ELF"]["sha256"],
            "PRG": c2["artifacts_after"]["PRG"]["sha256"],
            "boot_cycle_ratio": c2["final_product"]["boot_cycles"]["ratio"],
            "ordinary_text_margin": c2["final_product"]["bounded_owners"]["ordinary_text"]["margin_bytes"],
        },
        "card3": {
            "ELF": c3["artifacts_after"]["ELF"]["sha256"],
            "PRG": c3["artifacts_after"]["PRG"]["sha256"],
            "gc_reference_cycles": gc["reference_mean_cycles"],
            "gc_candidate_cycles": gc["candidate_mean_cycles"],
            "gc_cycle_ratio": gc["ratio"],
            "ordinary_text_margin": c3["final_product"]["bounded_owners"]["ordinary_text"]["margin_bytes"],
            "BSS_largest_hole": c3["final_product"]["bounded_owners"]["ordinary_BSS"]["largest_contiguous_hole_bytes"],
        },
        "card4": {
            "mutations": len(data["card4"]["mutations_rejected"]),
            "WPLTO_runs": data["card4"]["budget"]["WPLTO_runs"],
            "product_links": data["card4"]["budget"]["product_links"],
        },
        "card5": {
            "mutations": c5["mutation_suite"]["count"],
            "explicit_product_lifecycles": c5["facts"]["explicit_product_lifecycles"],
        },
        "card6": {
            "ELF": c6["artifacts_after"]["ELF"]["sha256"],
            "PRG": c6["artifacts_after"]["PRG"]["sha256"],
            "descriptor_users": values["final_trigger_population"],
            "encoded_source_tuple": values["packed_slice"]["encoded_source_tuple"],
            "boot_cycle_ratio": c6["final_product"]["boot_cycles"]["ratio"],
            "ordinary_text_margin": owners["ordinary_text"]["margin_bytes"],
            "BSS_margin": owners["ordinary_BSS"]["margin_bytes"],
            "island_margin": owners["resident_island"]["margin_bytes"],
            "E000_free": watch["free_bytes"],
            "E000_floor": watch["floor_bytes"],
            "capture_watch": watch["capture_watch_bytes"],
            "capture_watch_floor": watch["capture_watch_floor_bytes"],
        },
        "parked_restart_packages": ["A7 sentinel format", "A15 string-builder latch"],
    }


def receipt(data: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "lisp65-block-2.6-closure-v1",
        "status": "PASS: BLOCK 2.6 CLOSURE EVIDENCE GREEN",
        "facts": facts,
        "inputs": [
            {"role": name, "path": path.relative_to(ROOT).as_posix(),
             "sha256": sha(path)}
            for name, path in INPUTS.items()
        ] + [{"role": "parked_register", "path": PARKED.relative_to(ROOT).as_posix(),
              "sha256": sha(PARKED)}],
        "terminal_certification": {
            "required_consecutive_full_runs": 2,
            "command": "make -k check-source",
            "must_have_no_intervening_repair": True,
            "logs_are_handoff_metadata": True,
        },
        "owner_touchpoint": "accepting the report closes Block 2.6; v2.1 is not opened by this receipt",
    }


def render(facts: dict[str, Any]) -> str:
    c2, c3, c6 = facts["card2"], facts["card3"], facts["card6"]
    counts = facts["domain_contract"]
    c2_delta = (c2["boot_cycle_ratio"] - 1.0) * 100.0
    c3_delta = (c3["gc_cycle_ratio"] - 1.0) * 100.0
    c6_delta = (c6["boot_cycle_ratio"] - 1.0) * 100.0
    return f"""# Block 2.6 correctness and build integrity — block report

Status: **complete and review-ready — host-only, six cards green, zero physical-device contacts**.

Block 2.6 closes the correctness and build-integrity sweep commissioned after
DWX. Every product pair was world-bound before compilation, fully attributed,
qualified read-only and exercised through the packed-medium prefilter. This
report does not open v2.1; that remains the owner decision after review.

## Delivered results

1. **Symbol writes fail closed at their root.** Card 1 guards all three logical
   eval writers across four ABI sites; removing the `sf_setq` guard falls on an
   executed non-symbol assignment. The final pair is `{facts['card1']['ELF'][:8]}…` /
   `{facts['card1']['PRG'][:8]}…`.
2. **The F011 read layer reports errors instead of consuming bad bytes.** BUSY
   timeout and `$D082` errors are live, source-link state is a validated packed
   two-byte owner, and mapped bodies return failure for an ordinary caller to
   abort. A corrupted packed sector reaches `L65SYS DISK ERROR - CHECK MEDIA`.
   Boot cost changed by {c2_delta:.3f}% (ratio {c2['boot_cycle_ratio']:.9f});
   ordinary text ended exactly at its 32-byte floor.
3. **VM/frame hardening landed with a faster, complete GC.** Slot bounds,
   variadic frame depth, POP fail-stop and `%disk-poke` domain checks each have
   an executed sharp mutation. The flat mark fixpoint preserved the product
   graph and changed a forced collection from {c3['gc_reference_cycles']:,.0f}
   to {c3['gc_candidate_cycles']:,.0f} emulated CPU/DMA cycles
   ({c3_delta:.2f}%). Both fixed raw Bank-0 windows are linker-visible NOLOAD
   owners; each BSS side retains {c3['BSS_largest_hole']} bytes, and ordinary
   text reserve grew to {c3['ordinary_text_margin']} bytes.
4. **Compiler and Prelude semantics have one authority.** `%lcc-tail-if` uses
   `%lcc-rel8`; malformed cons operators fail rather than compile to `nil`;
   both `case` implementations use `consp`; `find`, `member` and `assoc` have
   one source. The executed durable domain matrix is now **{counts['error-raised']}
   error-raised / {counts['documented-permissive']} documented-permissive /
   {counts['silently-wrong']} silently-wrong**. The moved `find` list-domain
   cell is a stricter Tier-1 behavior and must be named in the next release notes.
5. **Product targets build or verify explicitly.** Six release lifecycles bind
   the product toolchain before work; parse-time shell and `/tmp` logs are gone,
   generated R6/G6 receipts require an explicit seal, and
   `docs/development.md` is the sole build-command authority. Eight mutations
   fall, including changed source attempting to verify old product bytes.
6. **Small hardening and provenance closed without spending E000.** The A15
   string latch was proportionately omitted; A10–A14 and the remaining A15
   work landed. The DMA seam preserves the encoded EDMA tuple `$8200` for all
   nine final-link users; ordinary `$20` byte-2 recomposition falls. The final
   pair is `{c6['ELF'][:8]}…` / `{c6['PRG'][:8]}…`, boot changed by
   {c6_delta:.3f}%, and all bounded owners are green: text
   {c6['ordinary_text_margin']}/32, BSS {c6['BSS_margin']}/5, Island
   {c6['island_margin']}/5, E000 {c6['E000_free']}/{c6['E000_floor']}, capture
   watch {c6['capture_watch']}/{c6['capture_watch_floor']}.

## Permanent gates and limits

Product-world identity is the sixth prelink authority category. Fixed raw
Bank-0 windows are linker-visible owners; mapped bodies return errors and never
abort or enter MAP recursively; Acceptance/Resume consumers are transitively
enumerated. The DWX packed-medium rows retain the corrupted-sector and
six-lines-then-`(print 9)` witnesses. Card 6 replaces the old DMA store/trigger
shape check with executed descriptor-value comparison over all nine users.

Two items leave the sweep as explicit restart packages: A7's terminal-sentinel
format card (the direct hot fetch check exceeded the 1.02× input wall), and the
A15 string-builder latch (requires a free ≥22-byte E000 reclaim or legal cold
placement). E000 has no growth budget while its capture watch is exactly on its
57-byte floor.

## Terminal certification and owner decision

The report-complete commit must pass two consecutive full
`make -k check-source` runs with Exit 0, no intervening repair and no tracked
tree change. Their wall times, line counts and SHA-256 log digests are handoff
metadata, not tracked inputs, so recording them cannot move the certified tree.

Accepting this report closes Block 2.6. Only the owner's acceptance opens v2.1
with the already prepared Comfort media card; this report itself commissions no
v2.1 product work.
"""


def selftest(data: dict[str, Any], parked: str) -> None:
    validate(data, parked)
    mutations: list[tuple[str, Any]] = []
    bad = deepcopy(data); bad["card1"]["status"] = "RED"; mutations.append(("card-omitted", bad))
    bad = deepcopy(data); bad["card2"]["attempt_accounting"]["device_contacts"] = 1; mutations.append(("device-contact-claimed", bad))
    bad = deepcopy(data); bad["card3"]["difference"]["unexplained_members"] = 1; mutations.append(("unexplained-difference", bad))
    bad = deepcopy(data); bad["domain_contract"]["counts"]["silently-wrong"] = 109; mutations.append(("domain-population-drift", bad))
    bad = deepcopy(data); bad["card5"]["mutation_suite"]["names"].remove("changed-source-verifies-old-bytes"); mutations.append(("build-integrity-mutation-omitted", bad))
    bad = deepcopy(data); bad["card6"]["final_product"]["small_hardening"]["descriptor_emission"]["executed_values"]["packed_slice"]["encoded_source_tuple"] = 0x2000; mutations.append(("EDMA-tuple-recomposed", bad))
    bad = deepcopy(data); bad["card6"]["final_product"]["e000_capture_watch"]["capture_watch_bytes"] = 56; mutations.append(("capture-watch-under-floor", bad))
    for name, changed in mutations:
        try:
            validate(changed, parked)
        except ClosureError:
            continue
        raise ClosureError(f"closure mutation survived: {name}")
    try:
        validate(data, parked.replace("A15 string-builder latch", "A15 removed"))
    except ClosureError:
        pass
    else:
        raise ClosureError("closure mutation survived: parked-restart-package-omitted")
    print(f"block-2.6 closure: SELFTEST PASS mutations={len(mutations) + 1}")


def run(write: bool) -> None:
    data = load_inputs()
    parked = PARKED.read_text(encoding="utf-8")
    selftest(data, parked)
    facts = validate(data, parked)
    expected_receipt = canonical(receipt(data, facts))
    expected_report = render(facts).encode()
    if write:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(expected_receipt)
        REPORT.write_bytes(expected_report)
    else:
        require(RECEIPT.read_bytes() == expected_receipt,
                "registered Block 2.6 closure receipt differs from derived result")
        require(REPORT.read_bytes() == expected_report,
                "registered Block 2.6 block report differs from derived result")
    print("block-2.6 closure: CHECK PASS cards=6 contacts=0 domain=546/178/110")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("selftest", "build", "check"))
    args = parser.parse_args()
    try:
        data = load_inputs()
        parked = PARKED.read_text(encoding="utf-8")
        if args.action == "selftest":
            selftest(data, parked)
        else:
            run(args.action == "build")
    except (OSError, UnicodeError, json.JSONDecodeError, ClosureError, KeyError) as error:
        print(f"block-2.6 closure: FAIL: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
