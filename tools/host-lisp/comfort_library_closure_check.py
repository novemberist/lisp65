#!/usr/bin/env python3
"""Packed-closure gate for the Comfort role on the 2.4.0 world (host only).

2.4.0 successor of comfort_closure_check.py on branch comfort-prepare-now@fa2a6eb8
(comfort-library card): plane config/c2-v240-public-plane, optional roles
041-ide/042-idex/043-m65d, compiler tier 045-lcc. Logic unchanged.

The v2.0 medium failed with "*** undefined function: %ide-line-net-depth":
the packed Comfort role called a scanner that only the IDE carried, and the
emitter accepted it because the scanner was declared an allowed external call.
This gate closes that class.  It reads the emitted Comfort role (manifest and
disassembly) and walks every CALL/TAILCALL target transitively:

  * a target defined by the role is walked further inside the role;
  * a target owned by the resident is walked further inside the resident
    (the resident image must be byte-identical to the accepted 2.4.0 plane);
  * a target owned by the product compiler tier (037-lcc, product shelf) is a
    boundary: that role's own closure belongs to its accepted build;
  * anything else fails: unowned, or owned only by an optional package
    (Comfort requires core only, so it must load with no package present).

It also fails on a duplicate owner: a published Comfort name that the
resident, one of the five packages, or the IDE/ide-extra/m65d roles also
publish.  A name an optional role carries anonymously (directory-only, its
own calls bound by entry reference) is reported, not failed: loading both
never gives the symbol two owners.  Finally, every CALLPRIM the role emits
must also be emitted by the accepted resident (so the product delivers it).

--expect-fail inverts the exit status for the mutation row.
"""
import argparse
import hashlib
import json
import os
import re
import sys

PLANE = "config/c2-v240-public-plane"
ACCEPTED_BLOB = os.path.join(PLANE, "plane", "stdlib-p0.blob.bin")
PACKAGES = ["buffer", "defstruct", "inspect", "place", "string-extra"]
OPTIONAL_ROLES = ["041-ide", "042-idex", "043-m65d"]
COMPILER_TIER = os.path.join(PLANE, "referenced", "045-lcc.manifest.json")

HEADER = re.compile(r"^\[(\d+)\]\s+(\S+)\s*$")
LITERAL = re.compile(r"^\s+lit\[(\d+)\]\s*=\s*\S+\s*;\s*(.*?)\s*$")
CALL = re.compile(r"\b(CALL|TAILCALL)\s+lit=(\d+)\b")
CALLPRIM = re.compile(r"\bCALLPRIM\s+prim=(\d+)(?::(\S+))?")


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def parse_disasm(path):
    """Return {object: {"calls": [(op, target)], "prims": {id: name}}}."""
    objects = {}
    current = None
    literals = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            header = HEADER.match(line)
            if header:
                current = {"calls": [], "prims": {}}
                objects[header.group(2)] = current
                literals = {}
                continue
            if current is None:
                continue
            literal = LITERAL.match(line)
            if literal:
                literals[int(literal.group(1))] = literal.group(2)
                continue
            call = CALL.search(line)
            if call:
                text = literals.get(int(call.group(2)), "")
                if not text or text.startswith('"'):
                    raise SystemExit("%s: call through a non-symbol literal: %s"
                                     % (path, line.strip()))
                current["calls"].append((call.group(1), text))
                continue
            prim = CALLPRIM.search(line)
            if prim:
                current["prims"][int(prim.group(1))] = prim.group(2) or "?"
    return objects


def published(manifest):
    return {entry["name"] for entry in manifest["entries"] if not entry.get("anonymous")}


def anonymous(manifest):
    return {entry["name"] for entry in manifest["entries"] if entry.get("anonymous")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="build/comfort-library-r1/role/repl-comfort",
                    help="emitted Comfort role prefix (manifest + disasm)")
    ap.add_argument("--resident", default="build/comfort-library-r1/resident/stdlib-p0",
                    help="emitted resident prefix (blob + manifest + disasm)")
    ap.add_argument("--expect-fail", action="store_true",
                    help="mutation row: succeed only if the gate rejects the role")
    ns = ap.parse_args(argv)

    failures = []
    notes = []

    resident_blob = ns.resident + ".blob.bin"
    if sha256(resident_blob) != sha256(ACCEPTED_BLOB):
        failures.append("resident image is not the accepted 2.4.0 plane (%s != %s)"
                        % (resident_blob, ACCEPTED_BLOB))
    resident_manifest = load_json(ns.resident + ".manifest.json")
    resident_code = parse_disasm(ns.resident + ".disasm.txt")
    resident_names = {entry["name"] for entry in resident_manifest["entries"]}

    role_manifest = load_json(ns.role + ".manifest.json")
    role_code = parse_disasm(ns.role + ".disasm.txt")
    role_names = {entry["name"] for entry in role_manifest["entries"]}
    role_published = published(role_manifest)
    if set(role_manifest.get("requires", [])) - {"core"}:
        failures.append("role requires more than core: %s" % role_manifest.get("requires"))

    tier = load_json(COMPILER_TIER)
    tier_names = published(tier)

    packages = {}
    for name in PACKAGES:
        packages[name] = load_json(os.path.join(PLANE, "libraries", name + ".manifest.json"))
    optional = {}
    for name in OPTIONAL_ROLES:
        optional[name] = load_json(os.path.join(PLANE, "referenced", name + ".manifest.json"))

    # ---- transitive callee closure --------------------------------------
    seen = set()
    order = sorted(role_names)
    reached = {"role": set(), "resident": set(), "compiler-tier": set()}
    while order:
        name = order.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in role_names:
            owner, code = "role", role_code
        elif name in resident_names:
            owner, code = "resident", resident_code
        elif name in tier_names:
            reached["compiler-tier"].add(name)
            continue
        else:
            continue          # reported at the call site below
        reached[owner].add(name)
        for op, target in code.get(name, {"calls": []})["calls"]:
            if target in role_names or target in resident_names or target in tier_names:
                order.append(target)
                continue
            owners = [pkg for pkg, manifest in packages.items() if target in published(manifest)]
            owners += [role for role, manifest in optional.items() if target in published(manifest)]
            if owners:
                failures.append("%s %s -> %s is owned only by optional %s; Comfort requires core only"
                                % (name, op, target, ", ".join(owners)))
            else:
                failures.append("unresolved callee: %s %s -> %s (no owner in the 2.4.0 resident, "
                                "the compiler tier, or the role)" % (name, op, target))

    # ---- duplicate owners -------------------------------------------------
    clash = role_published & resident_names
    if clash:
        failures.append("role overwrites resident owners: %s" % sorted(clash))
    for pkg, manifest in packages.items():
        clash = role_published & published(manifest)
        if clash:
            failures.append("role and package %s both publish %s" % (pkg, sorted(clash)))
    for role, manifest in optional.items():
        clash = role_published & published(manifest)
        if clash:
            failures.append("role and %s both publish %s" % (role, sorted(clash)))
        private = role_names & anonymous(manifest)
        for name in sorted(private):
            refs = [ref["caller"] for ref in manifest.get("directory_only", {}).get("entry_refs", [])
                    if ref.get("target") == name]
            notes.append("%s carries %s anonymously (directory-only; bound by entry reference from %s); "
                         "the role publishes its own copy, so the symbol has one owner"
                         % (role, name, ", ".join(sorted(set(refs))) or "no caller"))

    # ---- CALLPRIM delivery ------------------------------------------------
    resident_prims = {}
    for obj in resident_code.values():
        resident_prims.update(obj["prims"])
    for obj_name, obj in sorted(role_code.items()):
        for prim, pname in sorted(obj["prims"].items()):
            if prim not in resident_prims:
                failures.append("%s emits CALLPRIM %d (%s), which the accepted resident never emits"
                                % (obj_name, prim, pname))

    print("comfort-closure: role=%s objects=%d published=%s"
          % (ns.role, len(role_names), sorted(role_published)))
    print("comfort-closure: resident image = accepted 2.4.0 plane (%s)" % sha256(resident_blob)[:16])
    print("comfort-closure: reachable role=%d resident=%d compiler-tier=%s"
          % (len(reached["role"]), len(reached["resident"]), sorted(reached["compiler-tier"])))
    prims = sorted({p for obj in role_code.values() for p in obj["prims"]})
    print("comfort-closure: role CALLPRIMs %s all emitted by the accepted resident: %s"
          % (prims, "yes" if all(p in resident_prims for p in prims) else "no"))
    for note in notes:
        print("comfort-closure: note: " + note)
    for failure in failures:
        print("comfort-closure: FAIL: " + failure)
    status = "FAIL" if failures else "PASS"
    print("comfort-closure: %s (packages checked: %s; optional roles: %s)"
          % (status, ", ".join(PACKAGES), ", ".join(OPTIONAL_ROLES)))
    if ns.expect_fail:
        if failures:
            print("comfort-closure: mutation rejected as required")
            return 0
        print("comfort-closure: mutation NOT rejected")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
