#!/usr/bin/env python3
"""Unify input-capture layout, inventory and compiler membership."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STATUS = "PASS: INPUT-CAPTURE MEMBERSHIP CONSUMED BY REAL COMPILER PROFILE"


class MembershipError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise MembershipError(message)


def install_profile_projection(product: Any, base_link: Any) -> None:
    """Project the card's one build configuration into the real profile."""
    current = base_link.configure_profile
    if getattr(current, "_v160_input_capture_membership", False):
        return

    def configure_profile() -> tuple[str, ...]:
        features = tuple(current())
        feature = str(product.INPUT_CAPTURE_BUILD_CONFIGURATION["feature"])
        require(features.count(feature) == 0,
                "input-capture profile feature configured before projection")
        return (*features, feature)

    configure_profile._v160_input_capture_membership = True  # type: ignore[attr-defined]
    configure_profile._v160_input_capture_predecessor = current  # type: ignore[attr-defined]
    base_link.configure_profile = configure_profile


def validate_projection(product: Any, features: tuple[str, ...]) -> dict[str, Any]:
    config = product.INPUT_CAPTURE_BUILD_CONFIGURATION
    feature = str(config["feature"])
    allocated = tuple(str(name) for name in config["allocated"])
    require(features.count(feature) == 1,
            "real compiler profile did not consume capture feature exactly once")
    sources = product.source_list(features)
    closure = product.input_capture_consumption_closure(features, sources)
    inventory = product.input_capture_inventory_registration(features)
    layout = product.linker_script(ownership_opt_in=True)
    require(tuple(inventory["allocated"]) == allocated
            and all(layout.count(f"KEEP(*({name}))") == 1
                    for name in allocated),
            "layout/inventory did not derive from capture build configuration")

    rejected: list[str] = []
    without_feature = tuple(item for item in features if item != feature)
    try:
        product.input_capture_consumption_closure(
            without_feature, product.source_list(without_feature),
            layout_selected=True)
    except RuntimeError:
        rejected.append("layout-owner-absent-from-compiler-profile")
    capture = Path(config["source"]).resolve()
    base = Path(config["base_source"])
    without_owner = [path for path in sources
                     if Path(path).resolve() != capture]
    without_owner.append(str(base))
    try:
        product.input_capture_consumption_closure(
            features, without_owner, layout_selected=True)
    except RuntimeError:
        rejected.append("selected-profile-omits-layout-owner-source")

    valid_sections = [
        {"name": allocated[0], "bytes": 34},
        {"name": allocated[1], "bytes": 25},
    ]
    witness = product.input_capture_seed_size_witness(valid_sections, features)
    zero_rejections: dict[str, str] = {}
    for name in allocated:
        mutant = [dict(row) for row in valid_sections]
        next(row for row in mutant if row["name"] == name)["bytes"] = 0
        try:
            product.input_capture_seed_size_witness(mutant, features)
        except RuntimeError as error:
            message = str(error)
            require(str(config["name"]) in message and name in message,
                    "zero-size witness did not name its source owner")
            zero_rejections[name] = message
    require(rejected == ["layout-owner-absent-from-compiler-profile",
                         "selected-profile-omits-layout-owner-source"]
            and len(zero_rejections) == 2,
            "membership-consumption mutation accounting drift")
    return {"status": STATUS,
        "single_authority": "INPUT_CAPTURE_BUILD_CONFIGURATION",
        "build_configuration": {
            "name": config["name"], "feature": feature,
            "source": Path(config["source"]).relative_to(ROOT).as_posix(),
            "base_source": Path(config["base_source"]).relative_to(
                ROOT).as_posix(),
            "allocated": list(allocated)},
        "real_compiler_profile": {"feature_count": features.count(feature),
            "capture_source_consumed": str(config["source"]) in sources,
            "base_source_consumed": str(config["base_source"]) in sources,
            "source_count": len(sources)},
        "layout_inventory_compiler_closure": closure,
        "seed_size_witness": witness,
        "mutations_rejected": [*rejected,
            *[f"zero-size:{name}" for name in sorted(zero_rejections)]],
        "zero_size_messages": zero_rejections}
