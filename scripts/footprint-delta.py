#!/usr/bin/env python3
"""Compare two lisp65 footprint key/value reports."""
from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_FIELDS = [
    "status",
    "prg_bytes",
    "prg_file_end",
    "bank0_text_data_bytes",
    "bank0_bss_bytes",
    "stack_gap_bytes",
    "bank0_reserve_bytes",
    "boot_required_symbols",
    "boot_sym_headroom",
    "entries",
    "external_image_sympool_status",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--label", default="footprint-delta")
    p.add_argument("--candidate-exit", default="0")
    p.add_argument("--field", action="append", default=[], help="extra key to compare")
    return p.parse_args()


def read_report(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def maybe_int(value: str) -> int | None:
    if value in {"missing", ""}:
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def main() -> int:
    args = parse_args()
    base = read_report(args.baseline)
    cand = read_report(args.candidate)
    fields = DEFAULT_FIELDS + [f for f in args.field if f not in DEFAULT_FIELDS]

    lines = [
        f"label={args.label}",
        f"baseline={args.baseline}",
        f"candidate={args.candidate}",
        f"candidate_make_exit={args.candidate_exit}",
        f"baseline_status={base.get('status', 'missing')}",
        f"candidate_status={cand.get('status', 'missing')}",
        "",
        "Field deltas:",
    ]
    for field in fields:
        b = base.get(field, "missing")
        c = cand.get(field, "missing")
        bi = maybe_int(b)
        ci = maybe_int(c)
        if bi is not None and ci is not None:
            lines.append(f"{field}: baseline={b} candidate={c} delta={ci - bi}")
        else:
            lines.append(f"{field}: baseline={b} candidate={c}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"footprint-delta: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
