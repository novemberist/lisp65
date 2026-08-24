#!/usr/bin/env python3
"""Gate the identity-scoped source-owner conversion for input capture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_substitution_link as PRODUCT  # noqa: E402
import c2_v20_map_tuple_fix_card as MAP_FIX  # noqa: E402
import c2_v21_probe_oracle_root_product_config as MUTABLE  # noqa: E402
import c2_v160_abort_driver_relocation_config as ABORT  # noqa: E402


DRIVER = Path(__file__).resolve()
CAPTURE = "LISP65_V160_INPUT_CAPTURE"
MAPPED = "mapped-far-content-convergence"
CAPTURE_OWNER = "v160-input-capture"
STATUS = "PASS: SOURCE-OWNER MEMBERSHIP IS IDENTITY-SCOPED"


class ConversionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ConversionError(message)


def rows(value: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {row["name"]: row for row in value.get("scopes", [])}
    require(len(result) == len(value.get("scopes", [])),
            "source-owner registry contains duplicate identities")
    return result


def live_probe() -> dict[str, Any]:
    activation = PRODUCT.configure_input_capture()
    require(activation["feature"] == CAPTURE,
            "capture activation did not select its identity")
    MAP_FIX.configure_fix_source()
    MUTABLE.configure(PRODUCT)
    ABORT.configure(PRODUCT)
    selected = tuple(str(row["trigger"])
                     for row in PRODUCT.SOURCE_OWNER_SCOPES)
    dummy = {"product_build_id_hex": "0x00000000",
             "artifacts": {"shelf": {"bytes": 0}}}
    value = PRODUCT.source_owner_scope_gate(
        PRODUCT.definitions(dummy), selected, PRODUCT.source_list(selected))
    by_name = rows(value)
    require(MAPPED in by_name and CAPTURE_OWNER in by_name,
            "required source-owner identities absent")
    mapped = by_name[MAPPED]
    capture = by_name[CAPTURE_OWNER]
    live_capture_rows = [row for row in PRODUCT.SOURCE_OWNER_SCOPES
                         if row.get("name") == CAPTURE_OWNER]
    require(mapped["selected"] is True
            and PRODUCT.CONVERGENCE_FEATURE in mapped["defines"]
            and CAPTURE not in mapped["defines"]
            and capture["selected"] is True
            and capture["defines"] == [CAPTURE]
            and capture["sources"] == [
                "src/optional/c2_kernal_input_capture.s"]
            and len(live_capture_rows) == 1
            and live_capture_rows[0]["trigger"] == CAPTURE,
            "real source-owner consumer did not preserve identity domains")

    global_definitions = list(PRODUCT.CONVERGENCE_DEFINES)
    expected_mapped = [PRODUCT.CONVERGENCE_FEATURE,
        "LISP65_DMA_CONTENT_CONVERGENCE", "LISP65_C2_ASM_CONVERGENCE",
        "LISP65_C2_FULL_SPAN_CONVERGENCE", "LISP65_C2_MUTABLE_CPU_READS",
        "LISP65_C2_ABORT_DRIVER_FAR"]
    require(mapped["defines"] == sorted(expected_mapped)
            and CAPTURE in global_definitions,
            "configured writer family lost a legitimate owner feature")
    rejected: list[str] = []

    def validate(candidate: list[str]) -> None:
        require(CAPTURE not in candidate,
                "cross-domain aggregate escaped into mapped-far owner")

    validate(mapped["defines"])
    try:
        validate(global_definitions)
    except ConversionError:
        rejected.append("unfiltered-cross-domain-aggregate-copy")
    require(rejected == ["unfiltered-cross-domain-aggregate-copy"],
            "unfiltered aggregate-copy mutation survived")
    return {"status": STATUS,
        "real_consumer": "c2_v20_map_tuple_fix_card.configure_fix_source",
        "global_selected_definitions": global_definitions,
        "mapped_far_owner_definitions": mapped["defines"],
        "capture_owner_definitions": capture["defines"],
        "capture_owner_sources": capture["sources"],
        "writer_family": [
            "c2_v20_map_tuple_fix_card.configure_fix_source",
            "c2_v21_full_span_product_config.configure",
            "c2_v21_probe_oracle_root_product_config.configure",
            "c2_v160_abort_driver_relocation_config.configure",
            "c2_v160_abort_driver_relocation_config.restore_predecessor",
        ],
        "mutations_rejected": rejected,
        "rule": ("source-owner membership derives from the matching owner "
                 "identity, never a cross-domain aggregate")}


def run_probe() -> dict[str, Any]:
    result = subprocess.run([sys.executable, str(DRIVER), "_probe"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    require(result.returncode == 0,
            f"identity-scoped fresh-process probe red: {result.stderr}")
    value = json.loads(result.stdout)
    require(value.get("status") == STATUS,
            "identity-scoped probe returned wrong status")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "_probe"))
    if parser.parse_args().action == "_probe":
        print(json.dumps(live_probe(), sort_keys=True))
    else:
        value = run_probe()
        print("input-fidelity owner scope: CHECK PASS "
              f"mutations={len(value['mutations_rejected'])}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"input-fidelity owner scope: FIRST RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
