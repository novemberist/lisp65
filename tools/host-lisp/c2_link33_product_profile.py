#!/usr/bin/env python3
"""One machine-readable Link-33 product profile consumed by probe and link."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "config/c2-link33-product-profile.json"
FORMAT = "lisp65-c2-link33-product-profile-v1"


class ProfileError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def sha256() -> str:
    return hashlib.sha256(PROFILE.read_bytes()).hexdigest()


def value() -> dict[str, Any]:
    data = json.loads(PROFILE.read_text(encoding="utf-8"))
    require(data.get("format") == FORMAT, "Link-33 profile format drift")
    require(set(data) == {
        "format", "feature_defines", "append_slices",
        "session_emitter_state_bytes", "fixed_facade",
    }, "Link-33 profile field-set drift")
    features = data["feature_defines"]
    slices = data["append_slices"]
    require(isinstance(features, list) and len(features) == 11
            and len(set(features)) == 11
            and all(isinstance(item, str) and item.startswith("LISP65_")
                    for item in features),
            "Link-33 profile feature set is not exactly eleven unique defines")
    require(isinstance(slices, list) and len(slices) == 21
            and all(isinstance(item, list) and len(item) == 2
                    and all(isinstance(part, str) and part for part in item)
                    for item in slices)
            and len({item[0] for item in slices}) == 21,
            "Link-33 profile append ABI is not exactly 21 unique slices")
    require(data["session_emitter_state_bytes"] == 10,
            "Link-33 profile session-emitter state drift")
    require(data["fixed_facade"] == {
        "vector_count": 15, "handle_normalize_vma": 0xB5EE,
    }, "Link-33 profile facade contract drift")
    return data


def feature_defines() -> tuple[str, ...]:
    return tuple(value()["feature_defines"])


def append_slices() -> list[tuple[str, str]]:
    return [tuple(item) for item in value()["append_slices"]]


def configure(product: Any) -> None:
    """Apply the complete profile once; callers may not restate its fields."""
    data = value()
    product.configure_append_slices(append_slices())
    product.configure_session_emitter_state(
        data["session_emitter_state_bytes"])
    product.configure_e000_reopening()
    product.configure_bss_triage()
    require(len(product.C2_APPEND_SLICES) == 21
            and len(product.SESSION_SLICE_SPECS) == 46
            and len(product.BOOT_SLICE_SPECS) == 9
            and len(product.BOOT_DATA_SPECS) == 1
            and product.UNIQUE_SLICE_COUNT == 53,
            "Link-33 configured append/runtime ABI drift")
    require(product.SESSION_EMITTER_STATE_BYTES == 10,
            "Link-33 configured session-emitter state drift")
    require(product.host_facade_bytes() == 45
            and len(product.host_facade_vector_addresses()) == 15
            and product.host_facade_vector_addresses().get(
                "c2_facade_handle_normalize") == 0xB5EE,
            "Link-33 configured facade drift")


def receipt_identity() -> dict[str, Any]:
    return {
        "path": PROFILE.relative_to(ROOT).as_posix(),
        "bytes": PROFILE.stat().st_size,
        "sha256": sha256(),
        "format": FORMAT,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "sha256"))
    args = parser.parse_args()
    value()
    print(sha256() if args.action == "sha256"
          else "c2-link33-product-profile: CHECK PASS sha256=" + sha256())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ProfileError) as error:
        print(f"c2-link33-product-profile: FAIL {error}")
        raise SystemExit(2)
