#!/usr/bin/env python3
"""Compare two host L65M validators against fixtures and exhaustive mutations."""

from __future__ import annotations

import argparse
from ctypes import CDLL, POINTER, c_ubyte, c_uint16
from dataclasses import dataclass
import hashlib
from pathlib import Path
import sys


SUMMARY_WORDS = 30
STATUS_NUMBER = {
    name: number
    for number, name in enumerate((
        "L65M_OK",
        "L65M_ERR_ARGUMENT",
        "L65M_ERR_SOURCE",
        "L65M_ERR_CONTAINER",
        "L65M_ERR_HEADER",
        "L65M_ERR_SECTIONS",
        "L65M_ERR_STRINGS",
        "L65M_ERR_ENTRIES",
        "L65M_ERR_CODE",
        "L65M_ERR_INDEX",
        "L65M_ERR_NODE",
        "L65M_ERR_GRAPH",
        "L65M_ERR_PATCH",
        "L65M_ERR_REGION",
        "L65M_ERR_DIRECTORY",
        "L65M_ERR_SYMBOLS",
        "L65M_ERR_NAMEPOOL",
        "L65M_ERR_HEAP",
        "L65M_ERR_ARENA",
        "L65M_ERR_ROOTS",
        "L65M_ERR_STATE",
    ))
}
EXISTS_MODES = (("none", 0), ("some", 1), ("all", 2))
CAPACITY_MODES = (
    ("generous", 0),
    ("symbol-under", 1),
    ("symbol-exact", 2),
    ("symbol-over", 3),
    ("namepool-under", 4),
    ("namepool-exact", 5),
    ("namepool-over", 6),
)


@dataclass(frozen=True)
class DiffCase:
    name: str
    image: bytes
    expected_status: int | None
    expected_entries: int | None = None
    expected_patches: int | None = None
    expected_new_symbols: int | None = None


def load_library(path: Path):
    library = CDLL(str(path.resolve()))
    library.l65m_verdict_diff_run.argtypes = [
        POINTER(c_ubyte), c_uint16, c_ubyte, c_ubyte,
        POINTER(c_uint16), c_uint16,
    ]
    library.l65m_verdict_diff_run.restype = c_ubyte
    return library


def run(
    library, image: bytes, exists_mode: int, capacity_mode: int
) -> tuple[int, tuple[int, ...]]:
    if len(image) > 0xFFFF:
        raise ValueError(f"L65M fixture has {len(image)} bytes, maximum is 65535")
    buffer = (c_ubyte * max(1, len(image)))()
    if image:
        buffer[: len(image)] = image
    summary = (c_uint16 * SUMMARY_WORDS)()
    status = int(
        library.l65m_verdict_diff_run(
            buffer, len(image), exists_mode, capacity_mode, summary, SUMMARY_WORDS
        )
    )
    return status, tuple(summary)


def collect_cases(repo: Path):
    host_tools = repo / "tools" / "host-lisp"
    sys.path.insert(0, str(host_tools))
    from l65m_bulkread_fixtures import make_cases  # noqa: PLC0415
    from l65m_contract import (  # noqa: PLC0415
        RUNTIME_STATUS_BY_ERROR,
        check_fixture,
    )

    fixture, normative = check_fixture(
        repo / "tests" / "bytecode" / "formats" / "p0-disk-lib-v1.json"
    )
    bulk = make_cases()
    cases: list[DiffCase] = []
    for case in normative:
        status_name = (
            "L65M_OK" if case.valid else RUNTIME_STATUS_BY_ERROR[case.error]
        )
        cases.append(DiffCase(
            "fixture:" + case.id,
            case.image,
            STATUS_NUMBER[status_name],
            case.expected_entry_count if case.valid else None,
            case.expected_patch_count if case.valid else None,
        ))
    for case in bulk:
        cases.append(DiffCase(
            "bulk:" + case.name,
            case.image,
            STATUS_NUMBER[case.expected_status],
            expected_new_symbols=(
                case.expected_new_symbols
                if case.expected_status == "L65M_OK"
                else None
            ),
        ))

    truncations = 0
    bitflips = 0
    for golden_id, golden in fixture.goldens.items():
        for cut in range(len(golden.image)):
            cases.append(DiffCase(
                f"truncate:{golden_id}:{cut}", golden.image[:cut], None
            ))
            truncations += 1
        for offset in range(len(golden.image)):
            for bit in range(8):
                damaged = bytearray(golden.image)
                damaged[offset] ^= 1 << bit
                cases.append(DiffCase(
                    f"bitflip:{golden_id}:{offset}:{bit}", bytes(damaged), None
                ))
                bitflips += 1
    return cases, len(normative), len(bulk), truncations, bitflips


def v1_code_flags_ok(image: bytes) -> bool:
    blob_len = image[0] | (image[1] << 8)
    blob_start = 4
    metadata_start = blob_start + blob_len
    entry_count = image[metadata_start + 16] | (image[metadata_start + 17] << 8)
    entries_off = image[metadata_start + 24] | (image[metadata_start + 25] << 8)
    for entry_index in range(entry_count):
        entry = metadata_start + entries_off + entry_index * 8
        code_off = image[entry + 4] | (image[entry + 5] << 8)
        code_flags = image[blob_start + code_off + 3]
        if code_flags & ~1:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--baseline-so", type=Path, required=True)
    parser.add_argument("--current-so", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve()
    baseline_bytes = args.baseline_so.read_bytes()
    current_bytes = args.current_so.read_bytes()
    if hashlib.sha256(baseline_bytes).digest() == hashlib.sha256(current_bytes).digest():
        print("l65m-before-after-verdict-diff: baseline and current SO are identical",
              file=sys.stderr)
        return 2
    baseline = load_library(args.baseline_so)
    current = load_library(args.current_so)
    cases, normative_count, bulk_count, truncations, bitflips = collect_cases(repo)

    from l65m_contract import ContractError, validate_image  # noqa: PLC0415

    mismatches: list[tuple[object, ...]] = []
    oracle_accept = 0
    scenario_comparisons = 0
    for case in cases:
        try:
            oracle_summary = validate_image(case.image)
            oracle_ok = v1_code_flags_ok(case.image)
            if oracle_ok:
                oracle_accept += 1
            else:
                oracle_summary = None
        except ContractError:
            oracle_summary = None
            oracle_ok = False
        for exists_name, exists_mode in EXISTS_MODES:
            generous_before = run(baseline, case.image, exists_mode, 0)
            generous_after = run(current, case.image, exists_mode, 0)
            required_symbols = generous_before[1][24]
            required_name_bytes = generous_before[1][25]
            for capacity_name, capacity_mode in CAPACITY_MODES:
                before = (generous_before if capacity_mode == 0 else
                          run(baseline, case.image, exists_mode, capacity_mode))
                after = (generous_after if capacity_mode == 0 else
                         run(current, case.image, exists_mode, capacity_mode))
                scenario_comparisons += 1
                label = f"{case.name}:{exists_name}:{capacity_name}"
                if before[0] != after[0]:
                    mismatches.append((label, "before-after-status", before[0], after[0]))
                if (before[0] == STATUS_NUMBER["L65M_OK"]
                        and after[0] == STATUS_NUMBER["L65M_OK"]
                        and before[1] != after[1]):
                    mismatches.append((label, "before-after-plan", before[1], after[1]))

                if generous_before[0] == STATUS_NUMBER["L65M_OK"]:
                    expected = STATUS_NUMBER["L65M_OK"]
                    if capacity_name == "symbol-under" and required_symbols:
                        expected = STATUS_NUMBER["L65M_ERR_SYMBOLS"]
                    elif capacity_name == "namepool-under" and required_name_bytes:
                        expected = STATUS_NUMBER["L65M_ERR_NAMEPOOL"]
                    if before[0] != expected or after[0] != expected:
                        mismatches.append((label, "capacity-verdict", expected,
                                           before[0], after[0]))

                if capacity_mode != 0:
                    continue
                if (before[0] == STATUS_NUMBER["L65M_OK"]) != oracle_ok or (
                    after[0] == STATUS_NUMBER["L65M_OK"]
                ) != oracle_ok:
                    mismatches.append((label, "oracle-verdict", oracle_ok,
                                       before[0], after[0]))
                if case.expected_status is not None and (
                    before[0] != case.expected_status or after[0] != case.expected_status
                ):
                    mismatches.append((label, "fixture-status", case.expected_status,
                                       before[0], after[0]))
                if oracle_summary is not None and (
                    before[1][7] != len(oracle_summary.entry_names)
                    or after[1][7] != len(oracle_summary.entry_names)
                    or before[1][10] != oracle_summary.literal_patches
                    or after[1][10] != oracle_summary.literal_patches
                ):
                    mismatches.append((
                        label, "oracle-plan",
                        (len(oracle_summary.entry_names), oracle_summary.literal_patches),
                        (before[1][7], before[1][10]),
                        (after[1][7], after[1][10]),
                    ))
                if case.expected_entries is not None and (
                    before[1][7] != case.expected_entries
                    or after[1][7] != case.expected_entries
                ):
                    mismatches.append((label, "fixture-entry-count", case.expected_entries))
                if case.expected_patches is not None and (
                    before[1][10] != case.expected_patches
                    or after[1][10] != case.expected_patches
                ):
                    mismatches.append((label, "fixture-patch-count", case.expected_patches))
                if exists_mode == 0 and case.expected_new_symbols is not None and (
                    before[1][24] != case.expected_new_symbols
                    or after[1][24] != case.expected_new_symbols
                ):
                    mismatches.append((label, "fixture-new-symbols",
                                       case.expected_new_symbols,
                                       before[1][24], after[1][24]))

    output = (
        "l65m-before-after-verdict-diff: "
        f"cases={len(cases)} scenario-comparisons={scenario_comparisons} "
        f"exists-modes={len(EXISTS_MODES)} capacity-modes={len(CAPACITY_MODES)} "
        f"normative={normative_count} bulk={bulk_count} "
        f"truncations={truncations} bitflips={bitflips} "
        f"oracle-accept={oracle_accept} oracle-reject={len(cases) - oracle_accept} "
        f"mismatches={len(mismatches)}"
    )
    lines = [output]
    for mismatch in mismatches[:30]:
        lines.append("MISMATCH " + repr(mismatch))
    rendered = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return int(bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())
