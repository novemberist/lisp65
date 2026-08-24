#!/usr/bin/env python3
"""Close the renamed v1.4 library media over the immutable Link-92-r5 core."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_v112_candidate_media as OLD  # noqa: E402
import evidence_era as ERA  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.4.0-candidate-media-link92-r5-split"
BASE = BUILD / "base"
D2 = BUILD / "defstruct-acceptance"
BASE_MANIFEST = BUILD / "base-candidate-manifest.json"
D2_MANIFEST = BUILD / "defstruct-acceptance-manifest.json"
MANIFEST = BUILD / "candidate-manifest.json"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-split-media-receipt.json"
)
READBACK = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.12-link92-r5-split-media-readback-receipt.json"
)
STRING_MANIFEST = ROOT / (
    "build/post-promotion/v112/string-extra/string-extra.manifest.json"
)
INSPECT_MANIFEST = ROOT / "build/post-promotion/v112/inspect/inspect.manifest.json"
INSPECT_SUITE = ROOT / "tests/bytecode/libs/p0-inspect.json"
RELEASE_CONTRACT = ROOT / "config/c2-v112-release-closure.json"
PARITY_CONTRACT = ROOT / "config/v11-surface-delivery-parity.json"
D3_CONTRACT = ROOT / "config/c2-v112-link92-phase-d-d3.json"
USER_GUIDE = ROOT / "docs/user-guide.md"
GUIDE_ERA_COMMIT = "ac039d3b"
LANGUAGE_REFERENCE = ROOT / "docs/language-reference.md"
DEFSTRUCT_MANIFEST = ROOT / (
    "build/post-promotion/v110-performance/defstruct-candidate.manifest.json"
)
VARIANTS = {
    "base": (
        ("string-extra", "strx", "strextr", STRING_MANIFEST, ()),
        ("inspect", "inspect", "inspect", INSPECT_MANIFEST, ()),
    ),
    "defstruct": (
        ("string-extra", "strx", "strextr", STRING_MANIFEST, ()),
        ("inspect", "inspect", "inspect", INSPECT_MANIFEST, ()),
        ("defstruct", "defstruct", "dfstrct", DEFSTRUCT_MANIFEST, ()),
    ),
}
PUBLIC_SPLIT_FILES = (
    ROOT / "config/c2-v112-release-closure.json",
    ROOT / "config/v11-surface-delivery-parity.json",
    ROOT / "config/c2-v112-link92-phase-d-d3.json",
    ROOT / "docs/user-guide.md",
    ROOT / "docs/language-reference.md",
)
LEGACY_PUBLIC_NEEDLES = (
    "(require(quote comfort))",
    "(require 'comfort)",
    '"delivery": "comfort-library"',
    "post-promotion/v112/comfort/comfort.manifest.json",
    '"name": "comfort"',
)
TRACE_NAMES = {
    "%comfort-trace-remove", "%comfort-trace-wrapper-form",
    "%comfort-trace-install-form", "trace", "untrace",
}
INSPECT_NAMES = ("%comfort-callers-index", "who-calls")


class SplitMediaError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise SplitMediaError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def configure() -> dict[str, Any]:
    OLD.VARIANTS = VARIANTS
    OLD.configure_shared()
    # The split-media receipt is a sealed v1.4 readback.  Its shared-system
    # manifest deliberately names the Link-92 artifact world; asking the live
    # canonical-media producer to reconstruct that world would couple this
    # historical check to today's generated resident symbols.  Invert the
    # readback onto the persisted aggregate and its SHA-bound shared manifest
    # instead.  Current-source product builds have their own successor gates.
    sealed = load(OLD.RECEIPT)
    aggregate = load(OLD.MANIFEST)
    shared = load(OLD.MEDIA.MANIFEST)
    require(
        sealed == aggregate
        and aggregate.get("shared_media_manifest") == bind(OLD.MEDIA.MANIFEST)
        and aggregate.get("product_manifest") == bind(OLD.PRODUCT_MANIFEST)
        and shared.get("canonical_product") == bind(OLD.PRODUCT_MANIFEST)
        and shared.get("artifact_count") == 19,
        "immutable Link-92-r5 shared-system authority drift",
    )
    return shared


def public_split_gate(
    overrides: dict[Path, str] | None = None,
) -> dict[str, Any]:
    overrides = overrides or {}
    for path in PUBLIC_SPLIT_FILES:
        text = overrides.get(path, path.read_text(encoding="utf-8"))
        require(not any(needle in text for needle in LEGACY_PUBLIC_NEEDLES),
                f"legacy public comfort reference survived: {path}")
    return {
        "status": "passed-no-legacy-public-comfort-reference",
        "files": [path.relative_to(ROOT).as_posix() for path in PUBLIC_SPLIT_FILES],
        "needles_rejected": list(LEGACY_PUBLIC_NEEDLES),
    }


def public_split_mutations() -> dict[str, str]:
    result: dict[str, str] = {}
    target = PUBLIC_SPLIT_FILES[0]
    original = target.read_text(encoding="utf-8")
    for number, needle in enumerate(LEGACY_PUBLIC_NEEDLES, 1):
        try:
            public_split_gate({target: original + "\n" + needle})
        except SplitMediaError as error:
            result[f"legacy-public-comfort-{number}"] = str(error)
        else:
            raise SplitMediaError(
                f"legacy public comfort mutation survived: {needle}")
    require(len(result) == len(LEGACY_PUBLIC_NEEDLES),
            "public split mutation count drift")
    return result


def trace_descope_gate(
    overrides: dict[str, dict[str, Any] | str] | None = None,
) -> dict[str, Any]:
    overrides = overrides or {}
    suite = overrides.get("suite", load(INSPECT_SUITE))
    manifest = overrides.get("manifest", load(INSPECT_MANIFEST))
    release = overrides.get("release", load(RELEASE_CONTRACT))
    parity = overrides.get("parity", load(PARITY_CONTRACT))
    d3 = overrides.get("d3", load(D3_CONTRACT))
    # "Trace is not delivered in v1.4.0" is true of the world this receipt
    # sealed, and it stayed true until v1.5.0 delivered trace/untrace.  Read
    # against the living guide the sentence became a demand that today's
    # documentation deny a shipped feature, so the guide is read at the
    # commit that reclosed this medium.
    guide = overrides.get(
        "guide",
        ERA.era_blob(GUIDE_ERA_COMMIT, "docs/user-guide.md").decode("utf-8"))
    reference = overrides.get(
        "reference",
        ERA.era_blob(
            GUIDE_ERA_COMMIT, "docs/language-reference.md").decode("utf-8"))
    require(isinstance(suite, dict) and isinstance(manifest, dict)
            and isinstance(release, dict) and isinstance(parity, dict)
            and isinstance(d3, dict) and isinstance(guide, str)
            and isinstance(reference, str), "trace descope override type drift")
    suite_names = set(suite.get("functions", []))
    manifest_names = {row.get("name") for row in manifest.get("entries", [])}
    release_names = {row.get("name") for row in release.get(
        "unconditional_surface", [])} | set(release.get("public_surface", {}))
    parity_names = {row.get("name") for row in parity.get("claims", [])}
    d3_names = {row.get("id") for row in d3.get("libraries", {}).get("rows", [])}
    require(suite.get("sources") == ["lib/comfort-who-calls-generated.lisp"]
            and suite_names == set(INSPECT_NAMES),
            "inspect suite retained a descoped trace source/object")
    require(not TRACE_NAMES.intersection(manifest_names)
            and manifest.get("sources") == ["lib/comfort-who-calls-generated.lisp"],
            "inspect artifact retained a descoped trace object/source")
    require(not {"trace", "untrace"}.intersection(release_names)
            and release.get("trace_descope", {}).get("status")
            == "not-delivered-in-v1.4.0",
            "release contract retained or dimmed trace delivery")
    require(not {"trace", "untrace"}.intersection(parity_names),
            "surface parity retained descoped trace names")
    require(not {"trace", "trace-call", "untrace", "post-untrace"}
            .intersection(d3_names), "D3 retained descoped trace rows")
    require("(trace " not in guide and "(untrace " not in guide
            and "Function tracing is not delivered in v1.4.0" in guide,
            "user guide still advertises or fails to explain trace descope")
    public_section = reference.split("The released surface includes:", 1)[1]
    public_section = public_section.split("The complete native visibility", 1)[0]
    require("`trace`" not in public_section and "`untrace`" not in public_section
            and "Function tracing is not part of the v1.4.0 surface" in reference,
            "language reference still publishes or fails to explain trace descope")
    return {
        "status": "passed-trace-untrace-absent-from-v1.4-delivery",
        "inspect_objects": sorted(manifest_names),
        "public_names": sorted(release_names),
        "D3_rows": sorted(d3_names),
    }


def trace_descope_mutations() -> dict[str, str]:
    base = {
        "suite": load(INSPECT_SUITE),
        "manifest": load(INSPECT_MANIFEST),
        "release": load(RELEASE_CONTRACT),
        "parity": load(PARITY_CONTRACT),
        "d3": load(D3_CONTRACT),
        "guide": ERA.era_blob(
            GUIDE_ERA_COMMIT, "docs/user-guide.md").decode("utf-8"),
        "reference": ERA.era_blob(
            GUIDE_ERA_COMMIT, "docs/language-reference.md").decode("utf-8"),
    }
    result: dict[str, str] = {}

    def reject_trace(label: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        changed = deepcopy(base)
        mutate(changed)
        rejected(label, lambda: trace_descope_gate(changed), result)

    reject_trace("trace-source-survives", lambda x: x["suite"]["sources"].append(
        "lib/comfort-trace.lisp"))
    reject_trace("trace-suite-object-survives", lambda x: x["suite"]["functions"].append(
        "trace"))
    reject_trace("untrace-artifact-object-survives", lambda x: x["manifest"]["entries"].append(
        {"name": "untrace"}))
    reject_trace("trace-release-surface-survives", lambda x: x["release"][
        "unconditional_surface"].append({"kind": "macro", "name": "trace"}))
    reject_trace("untrace-parity-claim-survives", lambda x: x["parity"]["claims"].append(
        {"name": "untrace"}))
    reject_trace("trace-D3-row-survives", lambda x: x["d3"]["libraries"]["rows"].append(
        {"id": "trace"}))
    reject_trace("trace-guide-advertisement-survives", lambda x: x.__setitem__(
        "guide", x["guide"] + "\n(trace fn)\n"))
    reject_trace("trace-reference-surface-survives", lambda x: x.__setitem__(
        "reference", x["reference"].replace(
            "optional inspection from the inspect library: `who-calls`;",
            "optional inspection from the inspect library: `who-calls`, `trace`;")))
    require(len(result) == 8, "trace descope mutation count drift")
    return result


def shared_projection(shared: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: row[key] for key in ("role", "bytes", "sha256")}
        for row in shared["artifacts"]
    ]


def variant_gate(base: dict[str, Any], sibling: dict[str, Any]) -> dict[str, Any]:
    base_library = base.get("library", {})
    sibling_library = sibling.get("library", {})
    require(
        base.get("variant") == "base"
        and sibling.get("variant") == "defstruct"
        and base.get("shared_media") == sibling.get("shared_media")
        and base.get("shared_artifacts") == sibling.get("shared_artifacts")
        and set(base_library.get("artifacts", {})) == {"string-extra", "inspect"}
        and set(sibling_library.get("artifacts", {}))
            == {"string-extra", "inspect", "defstruct"}
        and all(base_library["artifacts"][name]["sha256"]
                == sibling_library["artifacts"][name]["sha256"]
                for name in ("string-extra", "inspect"))
        and [row["name"] for row in base_library["index_rows"]]
            == ["string-extra", "inspect"]
        and base_library["index_rows"] == sibling_library["index_rows"][:2]
        and all(not row["dependencies"] for row in sibling_library["index_rows"])
        and base.get("selection") == {
            "conditional_defstruct_public": False,
            "eligible_for_release_before_D2": True,
        }
        and sibling.get("selection") == {
            "conditional_defstruct_public": True,
            "eligible_for_release_before_D2": False,
        },
        "split media escaped its exact two-library plus defstruct delta",
    )
    return {
        "status": "passed-one-core-two-renamed-library-media-variants",
        "shared_roles": len(base["shared_artifacts"]),
        "base_index_rows": 2,
        "sibling_index_rows": 3,
        "third_differences": 0,
    }


def rejected(label: str, action: Callable[[], None], out: dict[str, str]) -> None:
    try:
        action()
    except SplitMediaError as error:
        out[label] = str(error)
    else:
        raise SplitMediaError(f"split-media mutation survived: {label}")


def mutations(base: dict[str, Any], sibling: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}

    def mutate(label: str, side: str, path: tuple[Any, ...], value: Any) -> None:
        left, right = deepcopy(base), deepcopy(sibling)
        cursor: Any = left if side == "base" else right
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        rejected(label, lambda: variant_gate(left, right), result)

    mutate("shared-product-divergence", "defstruct",
           ("shared_artifacts", 0, "sha256"), "0" * 64)
    mutate("shared-string-extra-divergence", "defstruct",
           ("library", "artifacts", "string-extra", "sha256"), "1" * 64)
    mutate("shared-inspect-divergence", "defstruct",
           ("library", "artifacts", "inspect", "sha256"), "2" * 64)
    mutate("legacy-comfort-row-survives", "base",
           ("library", "index_rows", 0, "name"), "comfort")
    changed = deepcopy(base["library"]["artifacts"])
    changed["defstruct"] = sibling["library"]["artifacts"]["defstruct"]
    mutate("defstruct-leaked-into-base", "base", ("library", "artifacts"), changed)
    changed = deepcopy(sibling["library"]["artifacts"])
    del changed["defstruct"]
    mutate("defstruct-absent-from-sibling", "defstruct",
           ("library", "artifacts"), changed)
    mutate("dependency-invented", "defstruct",
           ("library", "index_rows", 2, "dependencies"), [0])
    mutate("selection-dimmed", "defstruct",
           ("selection", "conditional_defstruct_public"), False)
    require(len(result) == 8, "split-media mutation count drift")
    return result


def make_variant(
    variant: str, shared_binding: dict[str, Any], shared_artifacts: list[dict[str, Any]],
    library: dict[str, Any], conditional: bool,
) -> dict[str, Any]:
    return {
        "format": "lisp65-c2.3-v1.12-link92-split-media-variant-v1",
        "status": "passed-closed-" + variant + "-split-media-candidate",
        "variant": variant,
        "shared_media": shared_binding,
        "shared_artifacts": shared_artifacts,
        "library": library,
        "selection": {
            "conditional_defstruct_public": conditional,
            "eligible_for_release_before_D2": not conditional,
        },
    }


def build() -> dict[str, Any]:
    require(not BUILD.exists(), "split media build is one-shot")
    surface_gate = public_split_gate()
    surface_mutations = public_split_mutations()
    trace_gate = trace_descope_gate()
    trace_mutations = trace_descope_mutations()
    shared = configure()
    build_id = OLD.product_build_id()
    base_library = OLD.build_library_variant("base", BASE, build_id)
    sibling_library = OLD.build_library_variant("defstruct", D2, build_id)
    shared_binding = bind(OLD.MEDIA.MANIFEST)
    projection = shared_projection(shared)
    base = make_variant("base", shared_binding, projection, base_library, False)
    sibling = make_variant(
        "defstruct", shared_binding, projection, sibling_library, True)
    BASE_MANIFEST.write_bytes(canonical(base))
    D2_MANIFEST.write_bytes(canonical(sibling))
    gate = variant_gate(base, sibling)
    rejected_mutations = mutations(base, sibling)
    value = {
        "format": "lisp65-c2.3-v1.12-link92-r5-split-media-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-renamed-media-over-immutable-link92-r5-core",
        "owner_authorization_commit": "f426f7c7",
        "product_manifest": bind(OLD.PRODUCT_MANIFEST),
        "shared_media_manifest": shared_binding,
        "base_manifest": bind(BASE_MANIFEST),
        "defstruct_acceptance_manifest": bind(D2_MANIFEST),
        "variant_gate": gate,
        "mutations_rejected": rejected_mutations,
        "public_split_gate": surface_gate,
        "public_split_mutations_rejected": surface_mutations,
        "trace_descope_gate": trace_gate,
        "trace_descope_mutations_rejected": trace_mutations,
        "execution_accounting": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "additional_product_cards": 0,
            "shared_system_rebuilds": 0,
            "base_library_rebuilds": 1,
            "defstruct_sibling_rebuilds": 1,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Host-closed renamed library media over immutable Link-92-r5. "
            "No device, selector, Halt, product-link or release claim."
        ),
    }
    MANIFEST.write_bytes(canonical(value))
    RECEIPT.write_bytes(canonical(value))
    return value


def rebuild_after_trace_descope() -> dict[str, Any]:
    require(BUILD.is_dir(), "prior split media closure is absent")
    require(BUILD.resolve().parent == (
        ROOT / "build/c2.3").resolve(), "split media rebuild path escaped build root")
    shutil.rmtree(BUILD)
    return build()


def reclose() -> dict[str, Any]:
    """Rebuild aggregates only; all product and library artifacts stay fixed."""
    require(BUILD.is_dir(), "split media artifacts are absent")
    surface_gate = public_split_gate()
    surface_mutations = public_split_mutations()
    trace_gate = trace_descope_gate()
    trace_mutations = trace_descope_mutations()
    shared = configure()
    build_id = OLD.product_build_id()
    base_library = OLD.existing_library_variant("base", BASE, build_id)
    sibling_library = OLD.existing_library_variant("defstruct", D2, build_id)
    shared_binding = bind(OLD.MEDIA.MANIFEST)
    projection = shared_projection(shared)
    base = make_variant("base", shared_binding, projection, base_library, False)
    sibling = make_variant(
        "defstruct", shared_binding, projection, sibling_library, True)
    BASE_MANIFEST.write_bytes(canonical(base))
    D2_MANIFEST.write_bytes(canonical(sibling))
    gate = variant_gate(base, sibling)
    rejected_mutations = mutations(base, sibling)
    value = {
        "format": "lisp65-c2.3-v1.12-link92-r5-split-media-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-renamed-media-over-immutable-link92-r5-core",
        "owner_authorization_commit": "f426f7c7",
        "product_manifest": bind(OLD.PRODUCT_MANIFEST),
        "shared_media_manifest": shared_binding,
        "base_manifest": bind(BASE_MANIFEST),
        "defstruct_acceptance_manifest": bind(D2_MANIFEST),
        "variant_gate": gate,
        "mutations_rejected": rejected_mutations,
        "public_split_gate": surface_gate,
        "public_split_mutations_rejected": surface_mutations,
        "trace_descope_gate": trace_gate,
        "trace_descope_mutations_rejected": trace_mutations,
        "execution_accounting": {
            "product_compiler_runs": 0,
            "product_linker_runs": 0,
            "additional_product_cards": 0,
            "shared_system_rebuilds": 0,
            "base_library_rebuilds": 0,
            "defstruct_sibling_rebuilds": 0,
            "aggregate_reclosures": 1,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Host-closed renamed library media over immutable Link-92-r5. "
            "No device, selector, Halt, product-link or release claim."
        ),
    }
    MANIFEST.write_bytes(canonical(value))
    RECEIPT.write_bytes(canonical(value))
    return value


def identity() -> dict[str, Any]:
    return {
        "product_manifest": bind(OLD.PRODUCT_MANIFEST),
        "shared_manifest": bind(OLD.MEDIA.MANIFEST),
        "shared_product_D81": bind(OLD.MEDIA.PRODUCT_D81),
        "shared_work_D81": bind(OLD.MEDIA.WORK_D81),
        "base_D81": bind(BASE / "lisp65-library.d81"),
        "base_index": bind(BASE / "l65index"),
        "base_string_extra": bind(BASE / "string-extra.l65s"),
        "base_inspect": bind(BASE / "inspect.l65s"),
        "sibling_D81": bind(D2 / "lisp65-library.d81"),
        "sibling_index": bind(D2 / "l65index"),
        "sibling_string_extra": bind(D2 / "string-extra.l65s"),
        "sibling_inspect": bind(D2 / "inspect.l65s"),
        "sibling_defstruct": bind(D2 / "defstruct.l65s"),
        "base_manifest": bind(BASE_MANIFEST),
        "sibling_manifest": bind(D2_MANIFEST),
        "aggregate_manifest": bind(MANIFEST),
        "persisted_receipt": bind(RECEIPT),
    }


def check() -> dict[str, Any]:
    configure()
    surface_gate = public_split_gate()
    surface_mutations = public_split_mutations()
    trace_gate = trace_descope_gate()
    trace_mutations = trace_descope_mutations()
    before = identity()
    base, sibling = load(BASE_MANIFEST), load(D2_MANIFEST)
    OLD.check_variant(base)
    OLD.check_variant(sibling)
    gate = variant_gate(base, sibling)
    rejected_mutations = mutations(base, sibling)
    value = load(MANIFEST)
    require(
        value.get("status") == "passed-renamed-media-over-immutable-link92-r5-core"
        and value.get("owner_authorization_commit") == "f426f7c7"
        and value.get("product_manifest") == bind(OLD.PRODUCT_MANIFEST)
        and value.get("shared_media_manifest") == bind(OLD.MEDIA.MANIFEST)
        and value.get("base_manifest") == bind(BASE_MANIFEST)
        and value.get("defstruct_acceptance_manifest") == bind(D2_MANIFEST)
        and value.get("variant_gate") == gate
        and value.get("mutations_rejected") == rejected_mutations
        and value.get("public_split_gate") == surface_gate
        and value.get("public_split_mutations_rejected") == surface_mutations
        and value.get("trace_descope_gate") == trace_gate
        and value.get("trace_descope_mutations_rejected") == trace_mutations
        and load(RECEIPT) == value,
        "split media aggregate receipt drift",
    )
    require(identity() == before, "split-media readback changed a SHA-fixed artifact")
    return value


def write_readback() -> dict[str, Any]:
    value = check()
    result = {
        "format": "lisp65-c2.3-v1.12-link92-r5-split-media-readback-v1",
        "recorded_on": "2026-08-07",
        "status": "passed-read-only-split-media-closure",
        "identity": identity(),
        "aggregate_status": value["status"],
        "index_rows": {"base": 2, "defstruct": 3},
        "resolver_contract": "declared-dependency-closure-only",
        "writes_during_readback": 0,
    }
    READBACK.write_bytes(canonical(result))
    return result


def check_readback() -> dict[str, Any]:
    check()
    value = load(READBACK)
    require(
        value.get("status") == "passed-read-only-split-media-closure"
        and value.get("identity") == identity()
        and value.get("index_rows") == {"base": 2, "defstruct": 3}
        and value.get("writes_during_readback") == 0,
        "split-media persisted readback drift",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("build", "rebuild-descope", "reclose", "readback", "check"))
    args = parser.parse_args()
    try:
        value = (build() if args.action == "build" else
                 rebuild_after_trace_descope()
                 if args.action == "rebuild-descope" else
                 reclose() if args.action == "reclose" else
                 write_readback() if args.action == "readback" else
                 check_readback())
        print("c2-v112-split-media: PASS " + value["status"])
        return 0
    except (SplitMediaError, OLD.MediaClosureError, OSError, ValueError,
            KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"c2-v112-split-media: FIRST RED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
