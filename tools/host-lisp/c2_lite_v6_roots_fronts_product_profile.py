#!/usr/bin/env python3
"""Canonical product profile for the roots/fronts successor link.

The Link-33 object protected the base product profile, but later C2-lite
features were layered by driver wrappers outside that object.  This object is
the complete current layer and is checked at the product-link entry before a
compiler or linker can run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / "config/c2-lite-v6-roots-fronts-product-profile.json"
DRIVER = ROOT / (
    "tools/host-lisp/c2_lite_v6_bank2_target_stage_successor_link.py")
FORMAT = "lisp65-c2-lite-v6-roots-fronts-product-profile-v1"


class ProfileError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size, "sha256": sha(path)}


def feature_row(path: Path) -> tuple[str, ...]:
    rows = [line.split("=", 1)[1] for line in
            path.read_text(encoding="utf-8").splitlines()
            if line.startswith("feature_defines=")]
    require(len(rows) == 1, f"{path}: feature_defines cardinality drift")
    values = tuple(rows[0].split(",")) if rows[0] else ()
    require(values and len(values) == len(set(values)),
            f"{path}: feature_defines are empty or duplicated")
    return values


def value() -> dict[str, Any]:
    data = json.loads(PROFILE.read_text(encoding="utf-8"))
    require(data.get("format") == FORMAT, "canonical profile format drift")
    require(set(data) == {
        "format", "authority", "feature_defines",
        "authorized_delta_from_link40", "driver_owned_features",
        "legacy_wrapper_gap_closed",
        "shape", "entry_rule", "historical_gap"},
        "canonical profile field-set drift")
    authority = data["authority"]
    require(set(authority) == {"green_wplto_receipt",
                               "green_wplto_profile",
                               "link40_predecessor_profile"},
            "canonical authority field-set drift")
    for record in authority.values():
        path = ROOT / record["path"]
        require(path.is_file() and sha(path) == record["sha256"],
                f"canonical profile authority drift: {path}")
    features = tuple(data["feature_defines"])
    require(len(features) == 19 and len(set(features)) == 19
            and all(isinstance(item, str) and item.startswith("LISP65_")
                    for item in features),
            "canonical feature set is not exactly 18 unique defines")
    wplto = ROOT / authority["green_wplto_profile"]["path"]
    predecessor = ROOT / authority["link40_predecessor_profile"]["path"]
    require(feature_row(wplto) == features,
            "canonical object differs from green WPLTO feature order")
    predecessor_features = feature_row(predecessor)
    delta = tuple(data["authorized_delta_from_link40"])
    require(set(features) == set(predecessor_features) | set(delta)
            and set(predecessor_features).isdisjoint(delta)
            and delta == ("LISP65_C2_LITE_BANK2_STAGING",
                          "LISP65_C2_LITE_V6_ROOTS_FRONTS_CORESIDENT"),
            "canonical feature delta is not exactly Bank-2 staging plus "
            "the approved fusion")
    driver_owned = tuple(data["driver_owned_features"])
    require(driver_owned == ("LISP65_C2_LITE_BANK2_STAGING",)
            and set(driver_owned).issubset(delta),
            "canonical driver-owned feature is not exactly Bank-2 staging")
    gap = tuple(data["legacy_wrapper_gap_closed"])
    require(gap == ("LISP65_C2_LITE_VM_ARITY_E000",)
            and set(gap).issubset(predecessor_features),
            "historical wrapper gap is not pinned to the Link-40 feature")
    require(data["shape"] == {
        "boot_family_slice_count": 12,
        "session_family_slice_count": 50,
        "unique_slice_count": 58,
        "session_family_bytes": 65438,
        "session_family_headroom_bytes": 98,
        "roots_fronts_slice_bytes": 1473,
    }, "canonical WPLTO shape drift")
    return data


def feature_defines() -> tuple[str, ...]:
    return tuple(value()["feature_defines"])


def check_legacy_configuration(features: Iterable[str]) -> dict[str, Any]:
    data = value()
    observed = tuple(features)
    canonical = tuple(data["feature_defines"])
    gap = set(data["legacy_wrapper_gap_closed"])
    require(len(observed) == len(set(observed)),
            "legacy wrapper emitted duplicate feature defines")
    driver_owned = set(data["driver_owned_features"])
    require(set(observed) == set(canonical) - gap - driver_owned,
            "legacy configuration drift exceeds the diagnosed wrapper gap "
            "and the one driver-owned Bank-2 slice installation")
    return {"status": "passed-diagnosed-wrapper-gap-only",
            "missing_from_legacy_wrapper": sorted(gap),
            "installed_by_driver_without_reconstructing_define":
                sorted(driver_owned)}


def compare_link_entry(features: Iterable[str]) -> None:
    require(tuple(features) == feature_defines(),
            "product-link entry differs from the canonical WPLTO feature set")


def source_gate() -> dict[str, Any]:
    source = DRIVER.read_text(encoding="utf-8")
    required = (
        "import c2_lite_v6_roots_fronts_product_profile as PROFILE",
        "profile = PROFILE.check()",
        "PROFILE.compare_link_entry(profile_features)",
        "B.configure_bank2_stage()",
    )
    require(all(token in source for token in required),
            "successor driver does not consume/check the canonical profile")
    forbidden = (
        "return (*features, RF.FEATURE)",
        "return (*features, B.FEATURE)",
        "EVAC.FEATURE",
        '"LISP65_C2_LITE_VM_ARITY_E000"',
    )
    require(not any(token in source for token in forbidden),
            "successor driver reconstructs a canonical profile field")
    return {"status": "passed-fixed-link-entry-source-gate",
            "driver": bind(DRIVER)}


def check() -> dict[str, Any]:
    data = value()
    return {
        "status": "passed-canonical-profile-and-fixed-entry-gate",
        "profile_object": {**bind(PROFILE), "format": FORMAT},
        "green_wplto_profile": bind(
            ROOT / data["authority"]["green_wplto_profile"]["path"]),
        "feature_defines": list(feature_defines()),
        "shape": data["shape"],
        "source_gate": source_gate(),
        "link33_gap_disposition": data["historical_gap"],
    }


def selftest() -> None:
    features = feature_defines()
    compare_link_entry(features)
    mutations = (
        features[:-1],
        (*features, "LISP65_FAKE_EXTRA"),
        (*features[:1], features[2], features[1], *features[3:]),
        (*features[:4], features[3], *features[5:]),
    )
    rejected = 0
    for mutation in mutations:
        try:
            compare_link_entry(mutation)
        except ProfileError:
            rejected += 1
    require(rejected == len(mutations),
            "canonical profile mutation suite did not close both edges")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "selftest"))
    args = parser.parse_args()
    if args.action == "selftest":
        selftest()
        print("c2-lite-v6-roots-fronts-product-profile: SELFTEST PASS "
              "mutations=4")
    else:
        result = check()
        print("c2-lite-v6-roots-fronts-product-profile: CHECK PASS sha256="
              + result["profile_object"]["sha256"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            ProfileError) as error:
        print(f"c2-lite-v6-roots-fronts-product-profile: FAIL {error}")
        raise SystemExit(2)
