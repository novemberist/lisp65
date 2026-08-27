#!/usr/bin/env python3
"""Preflight Block-3 Same-World media against physical Bank-2 ownership."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from elf_truth import ElfTruth  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/v1.7.0-pre-plan.md"
CARD = ARCH / "c2.3-v1.7-ide-idle-blink-product-card-r8-receipt.json"
PLANE = ROOT / "build/c2.3/v1.7-ide-idle-blink-current-plane/plane-preflight.json"
BUILD = ROOT / "build/c2.3/v1.7-block3-acceptance-media-preflight"
LOCAL_RECEIPT = BUILD / "preflight.json"
RECEIPT = ARCH / "c2.3-v1.7-block3-acceptance-media-preflight-first-red.json"
AUTHORIZATION = "3da72d96"
STATUS = "FIRST RED: BLOCK3 STATIC PLANE OVERLAPS LIVE MAPPED BANK2 FREIGHT"
CODE_BASE = 0x20000
MAPPED_SECTIONS = (
    ".lisp65_c2_mapped_far_service",
    ".lisp65_c2_mapped_product_cold",
)


class MediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MediaError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"input absent: {path}")
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def authority() -> dict[str, Any]:
    name = PLAN.relative_to(ROOT).as_posix()
    raw = subprocess.run(
        ["git", "show", f"{AUTHORIZATION}:{name}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE).stdout
    text = " ".join(raw.decode().lower().replace("`", "").replace(
        "*", "").split())
    for token in ("fresh same-world media", "block-3 hardware acceptance",
                  "matcher behavior in the line editor", "d5",
                  "no device contact begins before media identities"):
        require(token in text, f"Block-3 media authority absent: {token}")
    return {"authority": "git-blob", "commit": AUTHORIZATION, "path": name,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def image_rows(plane: dict[str, Any]) -> tuple[list[dict[str, Any]], bytes]:
    bank2_path = ROOT / plane["bank2"]["path"]
    raw = bank2_path.read_bytes()
    require(bind(bank2_path) == plane["bank2"],
            "card-3 Bank-2 plane identity drift")
    cursor = CODE_BASE
    rows: list[dict[str, Any]] = []
    for bound in plane["manifests"]:
        path = ROOT / bound["path"]
        require(bind(path) == bound, f"card-3 manifest drift: {path}")
        manifest = load(path)
        count = int(manifest["code_bytes"])
        name = str(manifest.get("name") or path.stem.removesuffix(".manifest"))
        rows.append({"name": name, "manifest": bound,
                     "start": cursor, "end_exclusive": cursor + count,
                     "bytes": count})
        cursor += count
    require(cursor - CODE_BASE == len(raw) == plane["geometry"]["bytes"]
            and len(rows) == plane["geometry"]["images"] == 6,
            "card-3 six-image geometry drift")
    return rows, raw


def owner_at(rows: list[dict[str, Any]], address: int) -> str:
    owners = [row["name"] for row in rows
              if row["start"] <= address < row["end_exclusive"]]
    require(len(owners) == 1, f"static-plane owner ambiguous at {address:#x}")
    return owners[0]


def mapped_rows(truth: ElfTruth, images: list[dict[str, Any]],
                plane: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    code_end = CODE_BASE + len(plane)
    for name in MAPPED_SECTIONS:
        raw = truth.section_bytes(name)
        stem = "__" + name.removeprefix(".")
        start = truth.symbol(stem + "_load_start").value
        end = truth.symbol(stem + "_load_end").value
        require(end - start == len(raw), f"mapped LMA extent drift: {name}")
        overlap_start = max(CODE_BASE, start)
        overlap_end = min(code_end, end)
        require(overlap_start < overlap_end,
                f"expected media collision disappeared: {name}")
        plane_offset = overlap_start - CODE_BASE
        section_offset = overlap_start - start
        observed = plane[plane_offset:plane_offset + overlap_end - overlap_start]
        expected = raw[section_offset:section_offset + len(observed)]
        differences = [index for index, pair in enumerate(zip(observed, expected))
                       if pair[0] != pair[1]]
        require(differences, f"overlap became byte-identical: {name}")
        first = differences[0]
        rows.append({
            "section": name,
            "VMA": truth.section(name).address,
            "LMA_start": start,
            "LMA_end_exclusive": end,
            "section_bytes": len(raw),
            "overlap_start": overlap_start,
            "overlap_end_exclusive": overlap_end,
            "overlap_bytes": len(observed),
            "different_bytes": len(differences),
            "static_owner": owner_at(images, overlap_start),
            "first_difference": {
                "physical_address": overlap_start + first,
                "static_plane_byte": observed[first],
                "mapped_section_byte": expected[first],
            },
            "mapped_sha256": hashlib.sha256(raw).hexdigest(),
            "static_overlap_sha256": hashlib.sha256(observed).hexdigest(),
            "mapped_overlap_sha256": hashlib.sha256(expected).hexdigest(),
        })
    return rows


def derive() -> dict[str, Any]:
    card = load(CARD)
    plane = load(PLANE)
    pair = card["frozen_pair_after"]
    require(
        card["status"] == "PASS: V1.7 IDE IDLE BLINK R8 FINAL WORLD GREEN"
        and pair == card["frozen_pair_before"]
        and card["scope"]["status"] == card["qualification"]["status"] == "PASS"
        and card["attempt_accounting"]["media_builds"] == 0
        and card["attempt_accounting"]["device_contacts"] == 0,
        "card-3 r8 closure is not the reviewed media source")
    elf = ROOT / pair["ELF"]["path"]
    prg = ROOT / pair["PRG"]["path"]
    require(bind(elf) == pair["ELF"] and bind(prg) == pair["PRG"],
            "reviewed r8 pair identity drift")
    images, bank2 = image_rows(plane)
    truth = ElfTruth.read(
        elf, llvm_readobj=ROOT / "tools/llvm-mos/bin/llvm-readobj",
        include_section_data=True)
    mapped = mapped_rows(truth, images, bank2)
    code_end = CODE_BASE + len(bank2)
    first_mapped = min(row["LMA_start"] for row in mapped)
    nominal_headroom = 0x30000 - code_end
    overflow = code_end - first_mapped
    require(len(bank2) == 52230 and nominal_headroom == 13306
            and overflow > 0
            and {row["static_owner"] for row in mapped}
                == {"c2-v112-product-compiler-tier"},
            "Block-3 media collision shape drift")

    materialized = bytearray(bank2)
    for row in mapped:
        raw = truth.section_bytes(row["section"])
        start = row["LMA_start"] - CODE_BASE
        materialized[start:start + len(raw)] = raw
    changed = sum(a != b for a, b in zip(bank2, materialized))
    require(changed == sum(row["different_bytes"] for row in mapped),
            "mapped materialization difference accounting drift")

    return {
        "format": "lisp65-c2-v17-block3-media-preflight-first-red-v1",
        "recorded_on": "2026-08-26",
        "status": STATUS,
        "authority": authority(),
        "reviewed_card": bind(CARD),
        "reviewed_pair": pair,
        "plane_preflight": bind(PLANE),
        "bank2_static_plane": plane["bank2"],
        "static_images": images,
        "physical_geometry": {
            "bank2_start": CODE_BASE,
            "bank2_end_exclusive": 0x30000,
            "static_plane_end_exclusive": code_end,
            "first_mapped_LMA": first_mapped,
            "nominal_tail_headroom_bytes": nominal_headroom,
            "static_plane_overflow_into_mapped_arena_bytes": overflow,
            "largest_contiguous_static_prefix_before_mapped_arena":
                first_mapped - CODE_BASE,
        },
        "collisions": mapped,
        "legacy_media_materialization_counterfactual": {
            "would_overwrite_static_bytes": changed,
            "static_plane_sha256": hashlib.sha256(bank2).hexdigest(),
            "materialized_sha256": hashlib.sha256(materialized).hexdigest(),
            "same_world": False,
        },
        "classification": {
            "product_defect_not_exonerated": True,
            "mechanism": ("the final product qualifies the 52,230-byte static "
                          "plane and mapped Bank-2 LMAs separately, but media "
                          "must deliver both into overlapping physical bytes"),
            "rule": ("aggregate Bank-2 tail headroom is not deliverable capacity "
                     "when another live owner begins inside that interval"),
            "required_disposition": ("reprice or relocate one owner; never overlay "
                                     "one reviewed world while claiming Same-World"),
        },
        "mutation_gate": {
            "shrink_static_end_to_first_mapped": "non-overlap",
            "move_mapped_start_to_static_end": "non-overlap",
            "current_candidate": "overlap-rejected",
        },
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
                       "product_cards": 0, "media_builds": 0,
                       "device_contacts": 0},
        "claim_limit": ("Host-only media preflight. No D81 was emitted and no "
                        "hardware acceptance claim is made."),
        "next": "review disposition of the cross-owner Bank-2 collision",
    }


def validate(value: dict[str, Any]) -> None:
    expected = derive()
    require(value == expected, "Block-3 media First-Red receipt drift")
    collisions = value["collisions"]
    require(value["status"] == STATUS and len(collisions) == 2
            and all(row["overlap_bytes"] > 0
                    and row["different_bytes"] > 0 for row in collisions)
            and value["legacy_media_materialization_counterfactual"]
                ["same_world"] is False
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "media_builds": 0, "device_contacts": 0},
            "Block-3 media First-Red claim drift")


def preflight() -> None:
    require(not BUILD.exists() and not RECEIPT.exists(),
            "Block-3 media preflight is one-shot")
    value = derive()
    BUILD.mkdir(parents=True)
    LOCAL_RECEIPT.write_bytes(canonical(value))
    RECEIPT.write_bytes(canonical(value))
    raise MediaError(
        "Same-World media impossible: static Bank-2 plane overlaps live MAP freight")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(load(LOCAL_RECEIPT) == value,
            "local and evidence First-Red receipts differ")
    print("v1.7 Block 3 media: FIRST RED VERIFIED media=0 device=0 "+
          f"overflow={value['physical_geometry']['static_plane_overflow_into_mapped_arena_bytes']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "check"))
    action = parser.parse_args().action
    if action == "preflight":
        preflight()
    else:
        check()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"v1.7 Block 3 media: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(2)
