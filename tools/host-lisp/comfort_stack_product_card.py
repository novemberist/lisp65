#!/usr/bin/env python3
"""Combined Comfort/SP successor: explicit authority, no implicit build replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import f011_buffered_repair_product_card as F
import hardware_sp_link_authority as SP

ROOT = F.ROOT
BUILD = ROOT / "build/v2.1/comfort-stack-product-r2"
PREFLIGHT = ROOT / "build/v2.1/comfort-stack-product-r2-preflight"
PREDECESSOR_BUILD = ROOT / "build/v2.1/renderer-branch-product-r1"
PREDECESSOR_PREFLIGHT = ROOT / "build/v2.1/renderer-branch-product-r1-preflight"
PREDECESSOR = {
    "BUILD": PREDECESSOR_BUILD,
    "PREFLIGHT": PREDECESSOR_PREFLIGHT,
    "PLANE": PREDECESSOR_PREFLIGHT / "setup-owned/static-plane/narrow-static",
    "ELF": PREDECESSOR_BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf",
    "PRG": PREDECESSOR_BUILD / "wplto/lisp65-c2-substitution-linked.prg",
    "PROFILE": PREDECESSOR_BUILD / "wplto/resolved-profile.txt",
    "PLANE_RECEIPT": PREDECESSOR_PREFLIGHT / "plane-receipt.json",
}
AUTHORIZATION = "8b6e08a3"
SERVICE_AUTHORIZATION = "eff4784e"
COMPOSITION_AUTHORIZATION = "df60d4b1"
DIRECT = ("src/eval.c", "src/io.c", "src/printer.c", "src/reader.c",
          "src/repl.c", "src/vm.c", "src/optional/c2_map_cpu_read.s")
HEADERS = ("src/hardware_stack.h", "src/repl.h", "src/reader.h", "src/io.h",
           "src/v2_native_function_dispatch.h", "src/f011_buffered_wait.h")
ADDITIONS = ("LISP65_COMFORT_TRAMPOLINE", "LISP65_HARDWARE_SP_GUARD",
             "LISP65_HARDWARE_SP_LINK_AUTHORITY")
ORIGINAL_CONFIGURE = F.configure
ORIGINAL_SOURCE_GATE = F.source_gate
PREDECESSOR_RTL = F.H.OUT / "sdcardio-03b24c6b.vhdl"
LINK_STAGE = None


def threshold_authority(target):
    require(LINK_STAGE == "measurement-seed", "final link awaits measured threshold authority")
    require(target == F.WPLTO / "resident-island-seed.prg", "unexpected seed target")
    return {"target": str(target.resolve()), "symbol": SP.SYMBOL,
            "threshold": 0, "stage": LINK_STAGE, "qualification_claim": False,
            "authorization": authority()}


def seed():
    """One seed WPLTO. Stop at its return, before any final C/LTO call."""
    global LINK_STAGE
    LINK_STAGE = "measurement-seed"
    configure()
    require(not F.INVOCATION.exists() and not BUILD.exists(), "seed budget already invoked")
    require(not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip(),
            "seed requires a clean commit-bound producer tree")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    remote = subprocess.check_output(["git", "rev-parse", "@{upstream}"], cwd=ROOT).decode().strip()
    require(head == remote, "producer commit must be remote-visible")
    pre = F.C.load(F.PREFLIGHT_RECEIPT)
    require(pre["authority"] == authority() and pre["toolchain"] == F.C.B.toolchain_identity(),
            "preflight authority/toolchain drift")
    for name, digest in F.C.B.profile_inputs(F.BOUND_PROFILE).items():
        if "/generated-product-sources/" not in name:
            require(F.C.bind(ROOT / name)["sha256"] == digest, "source changed after preflight: " + name)
    require(pre["profile"]["header_roots"] == [F.C.bind(ROOT / p) for p in HEADERS],
            "header changed after preflight")
    original = F.C.PRODUCT.compile_link
    entered = []
    class SeedComplete(BaseException):
        pass
    def build_seed(out, name, headers, artifacts, **kwargs):
        require(out == F.WPLTO and name == "resident-island-seed.prg" and not entered,
                "compiler call outside the one seed budget")
        entered.append(name)
        target = original(out, name, headers, artifacts, **kwargs)
        emission = SP.inspect_emission(Path(str(target) + ".elf"), F.C.B.READOBJ, 0)
        frozen = [F.C.bind(path) for path in
                  (target, Path(str(target) + ".elf"), Path(str(target) + ".lto.o"),
                   Path(str(target) + ".map"))]
        (BUILD / "measurement-seed.json").write_bytes(F.C.canonical({
            "status": "SEED BUILT; NO MEASUREMENT OR PRODUCT QUALIFICATION CLAIM",
            "authority": authority(), "commit": head, "artifacts": frozen,
            "threshold_emission": emission,
            "threshold": 0, "accounting": {"seed_WPLTO": 1, "final_C_LTO": 0,
                                            "product_links": 0, "host_images": 0}}))
        raise SeedComplete()
    F.INVOCATION.write_bytes(F.C.canonical({"status": "SEED INVOKED", "authority": authority(),
        "commit": head, "preflight": F.C.bind(F.PREFLIGHT_RECEIPT)}))
    F.C.PRODUCT.compile_link = build_seed
    try:
        try:
            F.C.B.child("_produce")
        except SeedComplete:
            require(entered == ["resident-island-seed.prg"], "seed stop missing")
        else:
            raise RuntimeError("producer returned without the bound seed stop")
    finally:
        F.C.PRODUCT.compile_link = original
        F.INVOCATION.write_bytes(F.C.canonical({"status": "SEED ATTEMPT FINISHED",
            "authority": authority(), "commit": head, "compiler_calls": entered,
            "seed_completed": (BUILD / "measurement-seed.json").exists(),
            "final_C_LTO": 0, "product_links": 0, "host_images": 0}))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def features(path):
    rows = [s.split("=", 1)[1] for s in path.read_text().splitlines()
            if s.startswith("feature_defines=")]
    require(len(rows) == 1 and rows[0], "feature authority absent/ambiguous")
    result = tuple(rows[0].split(","))
    require(len(result) == len(set(result)), "duplicate feature authority")
    return result


def authority():
    plan = "docs/planning/v2.0.0-pre-plan.md"
    raw = subprocess.check_output(["git", "show", AUTHORIZATION + ":" + plan], cwd=ROOT)
    # Bind the unique paragraph containing this card's complete budget, not
    # a matching phrase elsewhere in the accumulated planning history.
    sections = [p for p in raw.split(b"\n## ") if b"seed measurement image" in p
                and b"one seed WPLTO, one final C/LTO call, one product link" in p]
    require(len(sections) == 1, "combined budget paragraph absent/ambiguous")
    service = subprocess.check_output(["git", "show", SERVICE_AUTHORIZATION + ":" + plan], cwd=ROOT)
    require("## REVIEWER WORD — private native service".encode() in service
            and b"exactly this one private entry" in service, "private service authority absent")
    composition = subprocess.check_output(["git", "show", COMPOSITION_AUTHORIZATION + ":" + plan], cwd=ROOT)
    composition_sections = [p for p in composition.split(b"\n## ")
                            if b"one seed WPLTO plus the unspent" in p]
    require(len(composition_sections) == 1, "composition budget absent/ambiguous")
    require(F.C.bind(PREDECESSOR["ELF"])["sha256"] ==
            "c09d6e4d37a7e413133fc8541cc351e5cfc8274fefb7d3aaa325638f39391b2c",
            "renderer predecessor changed")
    return {"commit": AUTHORIZATION, "service_commit": SERVICE_AUTHORIZATION,
            "composition_commit": COMPOSITION_AUTHORIZATION,
            "composition_section_sha256": hashlib.sha256(composition_sections[0]).hexdigest(),
            "mode_contract": F.C.bind(ROOT / "config/comfort-entry-service.json"),
            "prior_consumption": {"seed_WPLTO": 1, "final_C_LTO": 0, "product_links": 0},
            "section_sha256": hashlib.sha256(sections[0]).hexdigest(),
            "predecessor": {n: F.C.bind(PREDECESSOR[n]) for n in ("ELF", "PRG")},
            "budget": {"seed_WPLTO": 1, "final_C_LTO": 1, "product_links": 1,
                       "host_check_images": 2, "device_contacts": 0}}


def bound_features():
    # Preserve the predecessor's producer-appended suffix. New explicit
    # arguments precede the inherited sequence, not its automatic features.
    expected = ADDITIONS + features(PREDECESSOR["PROFILE"])
    actual = features(F.BOUND_PROFILE)
    require(actual == expected, "successor features must be predecessor plus exactly the approved three")
    return actual


def feature_authority():
    actual = bound_features()
    return {"status": "PASS: DERIVED PREDECESSOR PLUS CLOSED COMFORT/SP FEATURES",
            "predecessor": F.C.bind(PREDECESSOR["PROFILE"]),
            "successor": F.C.bind(F.BOUND_PROFILE),
            "predecessor_feature_count": len(features(PREDECESSOR["PROFILE"])),
            "successor_feature_count": len(actual), "added": list(ADDITIONS)}


def source_preflight():
    """Use complete source identities, not the inherited 71/36 counters."""
    import tempfile
    leaf = F.C.B.PREV.CARD.CARD2.R2.CARD
    output = Path(tempfile.mkdtemp(prefix="source-population-", dir=PREFLIGHT))
    mapping = leaf.BASE.CHAIN.LINK.materialize_candidate_sources(output)
    selected = bound_features()
    sources = leaf.projected_source_list(mapping, selected)
    bound = F.C.B.profile_inputs(F.BOUND_PROFILE)
    require(all(Path(name).suffix in (".c", ".s", ".inc") for name in bound),
            "unclassified compiler-input category")
    expected = {name: digest for name, digest in bound.items() if Path(name).suffix != ".inc"}
    include_inputs = {name: digest for name, digest in bound.items() if Path(name).suffix == ".inc"}
    include_consumers = {}
    for name, digest in include_inputs.items():
        require(F.C.bind(ROOT / name)["sha256"] == digest, "assembly include authority drift")
        consumers = [str(path) for path in sources if Path(path).suffix == ".s"
                     and re.search(r'^\s*\.include\s+"' + re.escape(Path(name).name) + r'"',
                                   Path(path).read_text(), re.M)]
        require(consumers, "bound assembly include has no consuming translation unit: " + name)
        include_consumers[name] = consumers

    def identity(path):
        path = Path(path)
        if "generated-product-sources" in path.parts:
            path = F.WPLTO / "generated-product-sources" / path.name
        return str(path.relative_to(ROOT))

    actual = [identity(path) for path in sources]
    def check_population(population, flags, includes):
        require(len(population) == len(set(population))
                and set(population) == set(expected),
                "source identity population differs from producer profile: missing="
                + repr(sorted(set(expected) - set(population)))
                + " extra=" + repr(sorted(set(population) - set(expected))))
        require(tuple(flags) == ADDITIONS + features(PREDECESSOR["PROFILE"]),
                "feature identity population differs from closed successor authority")
        require(includes == include_inputs, "assembly include authority omitted or changed")
        require(str(F.C.PRODUCT.F011_COLD_SOURCE.relative_to(ROOT)) in population
                and F.C.PRODUCT.F011_COLD_FEATURE in flags, "F011 source/feature owner omitted")

    check_population(actual, selected, include_inputs)
    rejected = []
    for name, population, flags, includes in (
        [("source-omitted:" + name, [p for p in actual if p != name], selected, include_inputs) for name in actual]
        + [("feature-omitted:" + name, actual, [f for f in selected if f != name], include_inputs) for name in selected]
        + [("assembly-include-omitted:" + name, actual, selected,
            {p: digest for p, digest in include_inputs.items() if p != name}) for name in include_inputs]
    ):
        try:
            check_population(population, flags, includes)
        except RuntimeError:
            rejected.append(name)
        else:
            raise RuntimeError("population mutation survived: " + name)
    for path in sources:
        require(F.C.bind(Path(path))["sha256"] == expected[identity(path)],
                "projected source bytes differ: " + str(path))
    value = {"status": "PASS: IDENTITY-DERIVED COMPILER SOURCE/FEATURE POPULATION",
             "compiler_sources": {"total": len(sources), "generated": len(mapping)},
             "feature_count": len(selected), "feature_authority": feature_authority(),
             "assembly_include_consumers": include_consumers,
             "sources": [F.C.bind(Path(path)) for path in sources],
             "mutations_rejected": rejected}
    F.SOURCE_PREFLIGHT.write_bytes(F.C.canonical(value))
    return value


def profile(mapping=None):
    require(mapping is not None, "source projection must be producer-owned")
    generated = {p.name: p for p in mapping.values()}
    old = F.C.B.profile_inputs(PREDECESSOR["PROFILE"])
    lines = PREDECESSOR["PROFILE"].read_text().splitlines()
    authored, derived = [], []
    expected = features(PREDECESSOR["PROFILE"])
    for i, line in enumerate(lines):
        if line.startswith("feature_defines="):
            require(tuple(line.split("=", 1)[1].split(",")) == expected,
                    "source projection changed inherited feature population")
            lines[i] = "feature_defines=" + ",".join(ADDITIONS + expected)
        elif line.startswith("input_sha256="):
            name = line.split("=", 1)[1].split(":", 1)[0]
            path, successor, family = ROOT / name, name, authored
            if "/generated-product-sources/" in name:
                path = generated.get(Path(name).name,
                    PREDECESSOR_BUILD / "wplto/generated-product-sources" / Path(name).name)
                successor = str((F.WPLTO / "generated-product-sources" / path.name).relative_to(ROOT))
                family = derived
            digest = F.C.bind(path)["sha256"]
            lines[i] = "input_sha256=" + successor + ":" + digest
            if digest != old[name]:
                family.append(name)
    require(sorted(authored) == sorted(DIRECT), "uncommissioned authored source population: " + str(authored))
    F.BOUND_PROFILE.write_text("\n".join(lines) + "\n")
    return {"predecessor": F.C.bind(PREDECESSOR["PROFILE"]),
            "successor": F.C.bind(F.BOUND_PROFILE),
            "changed_authored_roots": sorted(authored), "changed_generated_roots": sorted(derived),
            "header_roots": [F.C.bind(ROOT / p) for p in HEADERS],
            "feature_count": len(bound_features())}


def source_gate():
    # Keep the repaired F011 source semantics live on this successor.
    result = ORIGINAL_SOURCE_GATE()
    subprocess.run([sys.executable, str(ROOT / "tools/host-lisp/bytecode_abi_ledger.py"),
                    "--selftest", "--require-staging-dispatch"], cwd=ROOT, check=True)
    for script, name in (("comfort_entry_service_gate.py", "registration"),
                         ("comfort_entry_context_gate.py", "admission-host")):
        out = PREFLIGHT / (name + ".json")
        subprocess.run([sys.executable, str(ROOT / "tools/host-lisp" / script),
                        "--output", str(out)], cwd=ROOT, check=True)
        result[name] = F.C.bind(out)
    result["final_elf_proofs_pending"] = True
    result["threshold_consumer"] = SP.selftest()
    return result


def configure():
    values = {"BUILD": BUILD, "PREFLIGHT": PREFLIGHT,
              "PLANE": PREFLIGHT / "setup-owned/static-plane/narrow-static",
              "WPLTO": BUILD / "wplto",
              "ELF": BUILD / "wplto/lisp65-c2-substitution-linked.prg.elf",
              "PRG": BUILD / "wplto/lisp65-c2-substitution-linked.prg",
              "PROFILE": BUILD / "wplto/resolved-profile.txt",
              "BOUND_PROFILE": PREFLIGHT / "bound-feature-profile.txt",
              "INVOCATION": PREFLIGHT / "candidate-invocation.json",
              "AUTHORIZATION": AUTHORIZATION,
              "PLAN_HEADER": "## BUDGET — combined Comfort trampoline / hardware-SP candidate",
              "FORMAT": "comfort-stack-product-r2",
              "STATUS": "PENDING: COMBINED COMFORT/SP QUALIFICATION",
              "DRIVER": Path(__file__).resolve(),
              "REPORT": ROOT / "docs/planning/v2.1-comfort-stack-product-report.md"}
    for name in ("PLANE_RECEIPT", "PREFLIGHT_RECEIPT", "SOURCE_PREFLIGHT", "PRELINK_RED", "DIFFERENCE", "RECEIPT"):
        values[name] = PREFLIGHT / (name.lower().replace("_", "-") + ".json")
    PREFLIGHT.mkdir(parents=True, exist_ok=True)
    for name, value in values.items():
        setattr(F, name, value)
    F.OLD.update(PREDECESSOR)
    F.authority, F.source_gate, F.profile = authority, source_gate, profile
    # These helpers are assigned into downstream consumers by configure_stack.
    F.C.B.bound_features = bound_features
    F.C.B.bound_feature_authority = feature_authority
    ORIGINAL_CONFIGURE()
    F.C.DIRECT = F.C.B.DIRECT_CARD6_SOURCES = DIRECT
    F.C.B.HEADER_ROOTS = HEADERS
    F.H.OUT = PREFLIGHT / "f011-regression"
    F.C.B.PREV.CARD.CARD2.R2.source_preflight = source_preflight
    F.C.PRODUCT.HARDWARE_SP_THRESHOLD_RESOLVER = threshold_authority


def archive_precompiler_stop():
    """Preserve a zero-compiler entry failure; never rearm a compiler attempt."""
    configure()
    record = F.C.load(F.INVOCATION)
    require(record.get("status") == "SEED ATTEMPT FINISHED"
            and record.get("compiler_calls") == []
            and record.get("seed_completed") is False
            and all(record.get(key) == 0 for key in
                    ("final_C_LTO", "product_links", "host_images"))
            and not BUILD.exists(), "not a proven precompiler stop; budget stays locked")
    attempt = 1
    while (PREFLIGHT / f"precompiler-stop-{attempt}.json").exists():
        attempt += 1
    target = PREFLIGHT / f"precompiler-stop-{attempt}.json"
    # Rename, do not rewrite, the original invocation evidence.
    F.INVOCATION.rename(target)
    print(json.dumps({"preserved": F.C.bind(target), "build_directory_absent": True,
                      "compiler_calls": [], "budget_consumed": [0, 0, 0]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["authority", "preflight", "seed", "archive-precompiler-stop"])
    args = parser.parse_args()
    if args.action == "authority":
        print(json.dumps(authority(), indent=2))
    elif args.action == "seed":
        seed()
    elif args.action == "archive-precompiler-stop":
        archive_precompiler_stop()
    else:
        configure()
        # Rebuild source-bound prerequisite evidence under THIS card's root;
        # never rewrite a qualified predecessor's receipt to fit new sources.
        F.H.OUT.mkdir(parents=True, exist_ok=True)
        rtl = F.H.OUT / PREDECESSOR_RTL.name
        if not rtl.exists():
            shutil.copyfile(PREDECESSOR_RTL, rtl)
        require(rtl.read_bytes() == PREDECESSOR_RTL.read_bytes(), "pinned RTL copy drift")
        F.H.main()
        require(not F.INVOCATION.exists() and not BUILD.exists(), "preflight retry after budget invocation forbidden")
        generated = PREFLIGHT / "profile-generated-sources"
        if generated.exists():
            attempt = 1
            while (PREFLIGHT / ("profile-generated-sources-attempt-" + str(attempt))).exists():
                attempt += 1
            # Preserve the failed, pre-budget projection as evidence. This is
            # not a seed rebuild or a read-only resume of a frozen product.
            generated.rename(PREFLIGHT / ("profile-generated-sources-attempt-" + str(attempt)))
        F.C.configure = configure
        F.C.preflight()


if __name__ == "__main__":
    main()
