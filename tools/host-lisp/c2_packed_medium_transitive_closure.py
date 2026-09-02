#!/usr/bin/env python3
"""Prove the transitive callee closure of one packed product/media world.

The older packed-callee gate proves the six resident product images.  A
medium may add independently compiled library objects, though, and a symbol
name in a manifest is not necessarily a published definition: private inline
objects deliberately retain names while their packed directory entries are
anonymous.  This gate composes both populations and classifies every emitted
CALL/TAILCALL against the definitions which the delivered world can actually
resolve.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import c2_packed_symbolic_callee_closure as PRODUCT  # noqa: E402
from v2_native_function_views_generated import ACTIVE_CALLPRIMS  # noqa: E402


FORMAT = "lisp65-packed-medium-transitive-callee-closure-v1"
PRODUCT_KEYS = ("stdlib-p0", "ide", "idex", "m65d", "buffer", "lcc")


class ClosureError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise ClosureError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = path.resolve().as_posix()
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def _artifact(path_text: str, manifest: Path) -> Path:
    path = Path(path_text)
    candidates = ([path] if path.is_absolute() else
                  [ROOT / path, manifest.parent / path])
    found = [candidate for candidate in candidates if candidate.is_file()]
    require(len(found) == 1, f"packed artifact path is not unique: {path_text}")
    return found[0]


def _definitions(manifest: Path, component: str) -> dict[str, Any]:
    value = load(manifest)
    entries = value.get("entries")
    require(isinstance(entries, list), f"entry inventory absent: {manifest}")
    public: list[dict[str, str]] = []
    private: list[dict[str, str]] = []
    objects: list[str] = []
    for row in entries:
        if not isinstance(row, dict) or row.get("kind") not in {
                "function", "macro"}:
            continue
        name = row.get("name")
        require(isinstance(name, str), f"packed entry lacks a name: {manifest}")
        objects.append(name)
        target = private if row.get("anonymous", False) else public
        target.append({"name": name, "component": component})
    overrides = value.get("override_exports", [])
    require(isinstance(overrides, list)
            and all(isinstance(name, str) for name in overrides),
            f"override export inventory drift: {manifest}")
    return {"manifest": bind(manifest), "objects": objects,
            "public": public, "private": private,
            "override_exports": overrides, "value": value}


def _product_rows(product_path: Path) -> tuple[list[dict[str, Any]],
                                                list[dict[str, Any]],
                                                list[dict[str, Any]]]:
    product = load(product_path)
    manifests = product.get("manifests")
    require(product.get("format") ==
            "lisp65-c2-product-substitution-artifacts-v1"
            and product.get("images") == len(PRODUCT_KEYS)
            and isinstance(manifests, list)
            and len(manifests) == len(PRODUCT_KEYS),
            "packed product identity drift")
    definitions: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    for key, binding in zip(PRODUCT_KEYS, manifests):
        require(isinstance(binding, dict) and isinstance(binding.get("path"), str),
                f"product manifest binding absent: {key}")
        manifest = _artifact(binding["path"], product_path)
        require(bind(manifest) == binding,
                f"product manifest identity drift: {key}")
        row = _definitions(manifest, f"product:{key}")
        definitions.append(row)
        components.append({"kind": "product-image", "key": key,
                           "manifest": row["manifest"],
                           "objects": len(row["objects"])})

    packed = PRODUCT.inventory(product_path, include_rows=True)
    rows = []
    for row in packed["call_sites"]:
        rows.append({**row, "component": f"product:{row['image']}"})
    return definitions, components, rows


def _external_calls(manifest: Path, component: str,
                    value: dict[str, Any]) -> tuple[dict[str, Any],
                                                    list[dict[str, Any]]]:
    blob_text = value.get("blob")
    require(isinstance(blob_text, str), f"packed blob absent: {manifest}")
    blob_path = _artifact(blob_text, manifest)
    blob = blob_path.read_bytes()
    require(value.get("abi_profile") == "dialect-v2"
            and value.get("artifact_role") == "disk-lib"
            and value.get("code_bytes") == len(blob)
            and value.get("blob_sha256") == hashlib.sha256(blob).hexdigest(),
            f"packed external blob identity drift: {manifest}")
    ledger = C._abi_ledger("dialect-v2", None)
    calls: list[dict[str, Any]] = []
    entries = value.get("entries", [])
    for ordinal, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("kind") not in {
                "function", "macro"}:
            continue
        name = entry.get("name")
        offset, length = entry.get("blob_offset"), entry.get("length")
        literals = entry.get("literals")
        require(isinstance(name, str) and isinstance(offset, int)
                and isinstance(length, int) and isinstance(literals, list)
                and offset >= 0 and length > 0
                and offset + length <= len(blob),
                f"packed external object bounds drift: {component}/{ordinal}")
        code = B.decode_code_object(blob[offset:offset + length])
        pc = 0
        while pc < len(code.payload):
            here = pc
            op, operand, pc = B.decode_instruction(
                code.payload, pc, profile_id="dialect-v2", abi_ledger=ledger)
            if op.mnemonic not in {"CALL", "TAILCALL"}:
                continue
            literal, argc = operand
            require(literal < len(literals),
                    f"packed call literal outside table: {component}/{name}")
            descriptor = literals[literal]
            require(isinstance(descriptor, dict)
                    and isinstance(descriptor.get("symbol"), str),
                    f"packed external call is not symbolic: {component}/{name}")
            calls.append({"component": component, "image": component,
                "caller": name, "pc": here, "opcode": op.mnemonic,
                "argc": argc, "literal": literal,
                "packed_literal_kind": "external-symbol",
                "target": descriptor["symbol"]})
    return ({"kind": "external-library", "key": component,
             "manifest": bind(manifest), "blob": bind(blob_path),
             "objects": sum(1 for row in entries if isinstance(row, dict)
                            and row.get("kind") in {"function", "macro"})}, calls)


def _compose(definitions: list[dict[str, Any]],
             components: list[dict[str, Any]], calls: list[dict[str, Any]],
             product_binding: dict[str, Any]) -> dict[str, Any]:
    """Compose already decoded owners and calls into one runtime world."""
    public_owners: dict[str, list[str]] = defaultdict(list)
    private_owners: dict[str, list[str]] = defaultdict(list)
    override_owners: dict[str, list[str]] = defaultdict(list)
    object_count = 0
    for row in definitions:
        object_count += len(row["objects"])
        for item in row["public"]:
            public_owners[item["name"]].append(item["component"])
        for item in row["private"]:
            private_owners[item["name"]].append(item["component"])
        for name in row["override_exports"]:
            require(name in {item["name"] for item in row["public"]},
                    f"override is not a public definition: {name}")
            override_owners[name].append(row["public"][0]["component"]
                if row["public"] else "")

    # A product may deliberately publish a late-bound base implementation and
    # one overriding successor (for example IDE/%ide-x and IDEX/%ide-x).  That
    # still has one runtime owner.  Unmarked duplicate publication does not.
    resolved_owners: dict[str, list[str]] = {}
    resolved_overrides: list[dict[str, Any]] = []
    for name, owners in public_owners.items():
        overrides = [owner for owner in owners
                     if name in override_owners and owner in override_owners[name]]
        if len(owners) == 1:
            resolved_owners[name] = owners
        elif len(overrides) == 1:
            resolved_owners[name] = overrides
            resolved_overrides.append({"name": name, "owner": overrides[0],
                                       "shadowed": [owner for owner in owners
                                                    if owner != overrides[0]]})

    duplicate_owners = [
        {"name": name, "owners": owners}
        for name, owners in sorted(public_owners.items())
        if name not in resolved_owners]
    classified: list[dict[str, Any]] = []
    for row in calls:
        kind, target = row["packed_literal_kind"], row["target"]
        if kind == 4:
            classification = "packed-direct-entry"
        elif kind == 6 or target in ACTIVE_CALLPRIMS:
            classification = "native"
        elif target in resolved_owners:
            classification = "published-cell"
        elif target in private_owners:
            classification = "anonymous-only"
        else:
            classification = "absent"
        classified.append({**row, "classification": classification,
                           "target_owner": resolved_owners.get(target, [])})

    failures = [row for row in classified if row["classification"] in {
        "anonymous-only", "absent"}]
    return {"format": FORMAT, "status": ("PASS" if not failures
            and not duplicate_owners else "FIRST RED"),
        "product": product_binding, "components": components,
        "object_count": object_count,
        "public_definition_count": len(public_owners),
        "private_definition_count": len(private_owners),
        "call_site_count": len(classified),
        "classification_counts": {name: sum(
            row["classification"] == name for row in classified)
            for name in ("packed-direct-entry", "native", "published-cell",
                         "anonymous-only", "absent")},
        "duplicate_public_owners": duplicate_owners,
        "resolved_overrides": resolved_overrides,
        "failures": failures,
        "rule": ("every packed object participates in one combined product/media "
                 "callee closure; a private anonymous object is not a published "
                 "definition"),
        "call_sites": classified}


def derive(product_path: Path,
           external_manifests: Iterable[Path] = ()) -> dict[str, Any]:
    definitions, components, calls = _product_rows(product_path)
    for ordinal, manifest in enumerate(external_manifests):
        component = f"medium:{ordinal}:{manifest.stem}"
        row = _definitions(manifest, component)
        definition_value = row.pop("value")
        definitions.append(row)
        packed, external_calls = _external_calls(
            manifest, component, definition_value)
        components.append(packed)
        calls.extend(external_calls)
    return _compose(definitions, components, calls, bind(product_path))


def require_closed(value: dict[str, Any]) -> None:
    require(value.get("status") == "PASS"
            and not value.get("duplicate_public_owners")
            and not value.get("failures"),
            "packed product/media callee closure is open: "
            + repr({"duplicates": value.get("duplicate_public_owners"),
                    "failures": value.get("failures")}))


def mutation_tests() -> list[str]:
    def owner(component: str, public: tuple[str, ...] = (),
              private: tuple[str, ...] = (),
              overrides: tuple[str, ...] = ()) -> dict[str, Any]:
        return {"objects": [*public, *private],
            "public": [{"name": name, "component": component}
                       for name in public],
            "private": [{"name": name, "component": component}
                        for name in private],
            "override_exports": list(overrides)}

    def call(target: str) -> dict[str, Any]:
        return {"component": "medium:fixture", "image": "medium:fixture",
            "caller": "%repl-step", "pc": 3, "opcode": "CALL", "argc": 0,
            "literal": 0, "packed_literal_kind": "external-symbol",
            "target": target}

    product = {"path": "synthetic-product", "bytes": 0, "sha256": "0" * 64}
    base = [owner("product:stdlib-p0", ("%repl-step", "%published",))]
    require_closed(_compose(base, [], [call("%published")], product))
    override = [*base, owner("product:idex", ("%published",),
                             overrides=("%published",))]
    require_closed(_compose(override, [], [call("%published")], product))

    cases = {
        "shared-source-private-sibling-is-not-publication":
            _compose([owner("product:stdlib-p0", ("%repl-step",),
                            ("%ide-line-net-depth",))], [],
                     [call("%ide-line-net-depth")], product),
        "missing-transitive-callee":
            _compose(base, [], [call("%missing")], product),
        "duplicate-resident-and-medium-owner":
            _compose([*base, owner("medium:fixture", ("%published",))], [],
                     [call("%published")], product),
    }
    rejected: list[str] = []
    for name, candidate in cases.items():
        try:
            require_closed(candidate)
        except ClosureError:
            rejected.append(name)
    require(rejected == list(cases), "packed-medium closure mutation survived")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("product", nargs="?", type=Path)
    parser.add_argument("--external-manifest", action="append", type=Path,
                        default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            rejected = mutation_tests()
            print("packed medium transitive closure selftest: PASS "
                  f"mutations={len(rejected)}")
            return 0
        require(args.product is not None,
                "product identity is required outside selftest")
        value = derive(args.product, args.external_manifest)
        value["mutations_rejected"] = mutation_tests()
        require_closed(value)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(canonical(value))
        print("packed medium transitive closure: PASS "
              f"objects={value['object_count']} calls={value['call_site_count']} "
              f"public={value['public_definition_count']}")
        return 0
    except (ClosureError, PRODUCT.ClosureError, B.DecodeError) as error:
        print(f"packed medium transitive closure: FIRST RED: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
