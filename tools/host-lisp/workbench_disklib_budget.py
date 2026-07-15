#!/usr/bin/env python3
"""Check Workbench on-demand disk-lib directory and runtime symbol budget."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import mvp_vm_stdlib_boot_budget as BB


def align8(n):
    return (n + 7) & ~7


def load_manifest(path):
    with open(path, "r", encoding="ascii") as f:
        manifest = json.load(f)
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("%s: missing entries list" % path)
    return manifest


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_int(manifest, name, default=0):
    image = manifest.get("external_image")
    if isinstance(image, dict) and image.get(name) is not None:
        return int(image[name])
    return int(manifest.get(name, default))


def parse_int_text(text):
    return int(str(text), 0)


def define_int(extra_cflags, name):
    match = re.search(
        r"(?:^|\s)-D%s=(0x[0-9a-fA-F]+|\d+)(?:\s|$)" % re.escape(name),
        extra_cflags,
    )
    if not match:
        raise SystemExit("extra cflags do not contain -D%s=<n>" % name)
    return parse_int_text(match.group(1))


def ext_code_budget(resident_code, disk_lib_code, disk_lib_metadata, limit):
    """Model the transactional disk-lib load and its committed allocation."""
    peak_used = resident_code + disk_lib_code + disk_lib_metadata
    post_used = resident_code + disk_lib_code
    return {
        "peak_used": peak_used,
        "peak_headroom": limit - peak_used,
        "post_used": post_used,
        "post_headroom": limit - post_used,
        "reclaimed": peak_used - post_used,
    }


def ext_code_sequence_budget(resident_code, disk_libs, limit):
    """Model ordered disk-lib loads; committed code survives each metadata reclaim."""
    committed = resident_code
    stages = []
    for index, (code_bytes, metadata_bytes) in enumerate(disk_libs):
        budget = ext_code_budget(committed, code_bytes, metadata_bytes, limit)
        budget["index"] = index
        budget["code_bytes"] = code_bytes
        budget["metadata_bytes"] = metadata_bytes
        stages.append(budget)
        committed = budget["post_used"]
    return stages


def ext_code_gate_failures(budget, min_peak_headroom, min_post_headroom):
    failures = []
    if budget["peak_headroom"] < min_peak_headroom:
        failures.append("peak")
    if budget["post_headroom"] < min_post_headroom:
        failures.append("post")
    return failures


def corrected_symbol_usage(
    static_symbols, static_namepool_bytes, symbol_correction, namepool_correction
):
    if symbol_correction < 0 or namepool_correction < 0:
        raise ValueError("composition corrections must be non-negative")
    return {
        "symbols": static_symbols + symbol_correction,
        "namepool_bytes": static_namepool_bytes + namepool_correction,
    }


def selftest():
    cases = 0

    named, literals = BB.manifest_symbols({
        "entries": [
            {"name": "public"},
            {"name": "%private", "anonymous": True},
        ],
        "literal_nodes": [
            {"kind": 4, "name": "literal"},
            {"kind": 8, "name": None},
        ],
    })
    assert named == {"public"} and literals == {"literal"}
    cases += 1

    budget = ext_code_budget(1000, 200, 300, 1700)
    expected = {
        "peak_used": 1500,
        "peak_headroom": 200,
        "post_used": 1200,
        "post_headroom": 500,
        "reclaimed": 300,
    }
    assert budget == expected
    cases += 1

    # Metadata is temporary: it changes peak use, but not the committed use.
    more_metadata = ext_code_budget(1000, 200, 350, 1700)
    assert more_metadata["peak_used"] == budget["peak_used"] + 50
    assert more_metadata["post_used"] == budget["post_used"]
    assert more_metadata["post_headroom"] == budget["post_headroom"]
    assert more_metadata["reclaimed"] == budget["reclaimed"] + 50
    cases += 1

    assert ext_code_gate_failures(budget, 201, 500) == ["peak"]
    cases += 1
    assert ext_code_gate_failures(budget, 200, 501) == ["post"]
    cases += 1
    assert ext_code_gate_failures(budget, 201, 501) == ["peak", "post"]
    cases += 1
    assert ext_code_gate_failures(budget, 200, 500) == []
    cases += 1

    stages = ext_code_sequence_budget(1000, [(200, 300), (100, 50)], 1800)
    assert stages == [
        {
            "peak_used": 1500,
            "peak_headroom": 300,
            "post_used": 1200,
            "post_headroom": 600,
            "reclaimed": 300,
            "index": 0,
            "code_bytes": 200,
            "metadata_bytes": 300,
        },
        {
            "peak_used": 1350,
            "peak_headroom": 450,
            "post_used": 1300,
            "post_headroom": 500,
            "reclaimed": 50,
            "index": 1,
            "code_bytes": 100,
            "metadata_bytes": 50,
        },
    ]
    cases += 1

    used = 320
    loads = []
    for entries in (140, 50):
        used = align8(used)
        used += entries
        loads.append(used)
    assert loads == [460, 514]
    assert align8(used) == 520
    cases += 1

    assert corrected_symbol_usage(672, 9060, 5, 51) == {
        "symbols": 677,
        "namepool_bytes": 9111,
    }
    cases += 1
    try:
        corrected_symbol_usage(1, 1, -1, 0)
        raise AssertionError("negative composition correction was accepted")
    except ValueError:
        pass
    cases += 1

    print("workbench-disk-lib-budget selftest: PASS cases=%d" % cases)
    return 0


def combined_runtime_symbol_budget(
    resident_manifest,
    disk_lib_manifests,
    extra_cflags,
    eval_c,
    native_sources,
    symbol_correction,
    namepool_correction,
):
    defines = BB.d_flags(extra_cflags)
    active_defines = set(defines)
    active_defines.add("__MEGA65__")
    native, _, _ = BB.native_symbols_from_sources(
        [eval_c, *native_sources],
        active_defines,
    )
    resident_entries, resident_literals = BB.manifest_symbols(resident_manifest)
    resident_runtime = native | resident_entries | resident_literals
    disk_runtime = set()
    for manifest in disk_lib_manifests:
        disk_entries, disk_literals = BB.manifest_symbols(manifest)
        disk_runtime.update(disk_entries)
        disk_runtime.update(disk_literals)
    all_runtime = resident_runtime | disk_runtime
    disk_new = disk_runtime - resident_runtime
    static_namepool_bytes = BB.namepool_bytes(all_runtime)
    corrected = corrected_symbol_usage(
        len(all_runtime), static_namepool_bytes,
        symbol_correction, namepool_correction,
    )
    return {
        "symbols": corrected["symbols"],
        "static_symbols": len(all_runtime),
        "symbol_correction": symbol_correction,
        "namepool_bytes": corrected["namepool_bytes"],
        "static_namepool_bytes": static_namepool_bytes,
        "namepool_correction": namepool_correction,
        "native_symbols": len(native),
        "resident_symbols": len(resident_entries | resident_literals),
        "disk_symbols": len(disk_runtime),
        "disk_new_symbols": len(disk_new),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--resident-manifest")
    ap.add_argument(
        "--disk-lib-manifest",
        action="append",
        help="ordered disk-lib manifest; repeat for cumulative loads",
    )
    ap.add_argument("--extra-cflags")
    ap.add_argument("--boot-align8", action="store_true")
    ap.add_argument("--eval-c", type=Path, default=Path("src/eval.c"))
    ap.add_argument("--native-c", type=Path, action="append", default=[])
    ap.add_argument("--symbol-correction", type=int, default=0)
    ap.add_argument("--namepool-correction", type=int, default=0)
    ap.add_argument("--min-load-headroom", type=int, default=0)
    ap.add_argument("--min-post-align-headroom", type=int, default=0)
    ap.add_argument("--min-codebuf-headroom", type=int, default=0)
    ap.add_argument(
        "--min-ext-code-headroom",
        type=int,
        help="compatibility alias for --min-ext-code-peak-headroom",
    )
    ap.add_argument("--min-ext-code-peak-headroom", type=int)
    ap.add_argument("--min-ext-code-post-headroom", type=int, default=0)
    ap.add_argument("--min-symbol-headroom", type=int, default=0)
    ap.add_argument("--min-namepool-headroom", type=int, default=0)
    ap.add_argument("--disk-file-max", default="0x9300")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    missing = [
        option
        for option, value in (
            ("--resident-manifest", args.resident_manifest),
            ("--disk-lib-manifest", args.disk_lib_manifest),
            ("--extra-cflags", args.extra_cflags),
        )
        if value is None
    ]
    if missing:
        ap.error("the following arguments are required: %s" % ", ".join(missing))
    if (
        args.min_ext_code_headroom is not None
        and args.min_ext_code_peak_headroom is not None
    ):
        ap.error(
            "--min-ext-code-headroom and --min-ext-code-peak-headroom "
            "are mutually exclusive"
        )
    min_ext_code_peak_headroom = args.min_ext_code_peak_headroom
    if min_ext_code_peak_headroom is None:
        min_ext_code_peak_headroom = args.min_ext_code_headroom or 0

    cap = define_int(args.extra_cflags, "VM_DIR_MAX")
    codebuf = define_int(args.extra_cflags, "VM_CODEBUF")
    ext_code_limit = define_int(args.extra_cflags, "SYMPOOL_EXT_OFF")
    max_sym = define_int(args.extra_cflags, "MAX_SYM")
    namepool = define_int(args.extra_cflags, "NAMEPOOL")
    resident_manifest = load_manifest(args.resident_manifest)
    disk_lib_manifests = [load_manifest(path) for path in args.disk_lib_manifest]
    resident = len(resident_manifest["entries"])
    disk_lib_entries = [len(manifest["entries"]) for manifest in disk_lib_manifests]
    disk_lib = sum(disk_lib_entries)
    resident_code_bytes = image_int(resident_manifest, "code_bytes")
    disk_lib_code_bytes = [image_int(manifest, "code_bytes") for manifest in disk_lib_manifests]
    disk_lib_metadata_bytes = [image_int(manifest, "metadata_bytes") for manifest in disk_lib_manifests]
    disk_lib_file_bytes = [image_int(manifest, "bytes") for manifest in disk_lib_manifests]
    disk_file_max = parse_int_text(args.disk_file_max)
    ext_code_stages = ext_code_sequence_budget(
        resident_code_bytes,
        list(zip(disk_lib_code_bytes, disk_lib_metadata_bytes)),
        ext_code_limit,
    )
    ext_code = min(ext_code_stages, key=lambda stage: stage["peak_headroom"])
    ext_code_post = ext_code_stages[-1]
    ext_code_gate = dict(ext_code)
    ext_code_gate["post_used"] = ext_code_post["post_used"]
    ext_code_gate["post_headroom"] = ext_code_post["post_headroom"]
    start = align8(resident) if args.boot_align8 else resident
    load_stages = []
    load_used = start
    for entries in disk_lib_entries:
        load_used = align8(load_used)
        load_used += entries
        load_stages.append(load_used)
    post_align_used = align8(load_used)
    worst_codebuf_name = "-"
    worst_codebuf_required = 0
    worst_codebuf_lits = 0
    for manifest in disk_lib_manifests:
        for entry in manifest["entries"]:
            lit_count = int(entry.get("lit_count", 0))
            required = 7 + 2 * lit_count + 3
            if required > worst_codebuf_required:
                worst_codebuf_required = required
                worst_codebuf_lits = lit_count
                worst_codebuf_name = entry.get("name", "-")

    if load_used + args.min_load_headroom > cap:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL load_used=%d headroom=%d cap=%d "
            "(resident=%d start=%d disk_lib=%d)"
            % (load_used, cap - load_used, cap, resident, start, disk_lib)
        )
    if post_align_used + args.min_post_align_headroom > cap:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL post_align_used=%d headroom=%d cap=%d "
            "(resident=%d start=%d disk_lib=%d)"
            % (post_align_used, cap - post_align_used, cap, resident, start, disk_lib)
        )
    if worst_codebuf_required + args.min_codebuf_headroom > codebuf:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL codebuf_required=%d headroom=%d cap=%d "
            "(entry=%s lit_count=%d)"
            % (
                worst_codebuf_required,
                codebuf - worst_codebuf_required,
                codebuf,
                worst_codebuf_name,
                worst_codebuf_lits,
            )
        )
    ext_code_failures = ext_code_gate_failures(
        ext_code_gate,
        min_ext_code_peak_headroom,
        args.min_ext_code_post_headroom,
    )
    if "peak" in ext_code_failures:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL ext_code_peak_used=%d "
            "ext_code_peak_headroom=%d min_peak_headroom=%d "
            "ext_code_post_used=%d ext_code_post_headroom=%d "
            "ext_code_reclaimed_bytes=%d cap=%d "
            "(resident_code=%d disk_lib_code=%d disk_lib_metadata=%d)"
            % (
                ext_code["peak_used"],
                ext_code["peak_headroom"],
                min_ext_code_peak_headroom,
                ext_code_post["post_used"],
                ext_code_post["post_headroom"],
                ext_code["reclaimed"],
                ext_code_limit,
                resident_code_bytes,
                ext_code["code_bytes"],
                ext_code["metadata_bytes"],
            )
        )
    if "post" in ext_code_failures:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL ext_code_post_used=%d "
            "ext_code_post_headroom=%d min_post_headroom=%d "
            "ext_code_peak_used=%d ext_code_peak_headroom=%d "
            "ext_code_reclaimed_bytes=%d cap=%d "
            "(resident_code=%d disk_lib_code=%d disk_lib_metadata=%d)"
            % (
                ext_code_post["post_used"],
                ext_code_post["post_headroom"],
                args.min_ext_code_post_headroom,
                ext_code["peak_used"],
                ext_code["peak_headroom"],
                ext_code_post["reclaimed"],
                ext_code_limit,
                resident_code_bytes,
                ext_code_post["code_bytes"],
                ext_code_post["metadata_bytes"],
            )
        )
    if max(disk_lib_file_bytes) > disk_file_max:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL disk_lib_file_bytes=%d cap=%d "
            "(scratch file window too small)"
            % (max(disk_lib_file_bytes), disk_file_max)
        )

    symbols = combined_runtime_symbol_budget(
        resident_manifest,
        disk_lib_manifests,
        args.extra_cflags,
        args.eval_c,
        args.native_c,
        args.symbol_correction,
        args.namepool_correction,
    )
    symbol_headroom = max_sym - int(symbols["symbols"])
    namepool_headroom = namepool - int(symbols["namepool_bytes"])
    if symbol_headroom < args.min_symbol_headroom:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL runtime_symbols=%d headroom=%d cap=%d "
            "(static=%d correction=%d disk_new=%d)"
            % (
                symbols["symbols"],
                symbol_headroom,
                max_sym,
                symbols["static_symbols"],
                symbols["symbol_correction"],
                symbols["disk_new_symbols"],
            )
        )
    if namepool_headroom < args.min_namepool_headroom:
        raise SystemExit(
            "workbench-disk-lib-budget: FAIL runtime_namepool=%d headroom=%d cap=%d "
            "(static=%d correction=%d disk_new=%d)"
            % (
                symbols["namepool_bytes"],
                namepool_headroom,
                namepool,
                symbols["static_namepool_bytes"],
                symbols["namepool_correction"],
                symbols["disk_new_symbols"],
            )
        )

    report = {
        "schema": "lisp65-workbench-library-composition-budget-v1",
        "status": "pass",
        "inputs": {
            "resident_manifest": {
                "path": args.resident_manifest,
                "sha256": sha256_file(args.resident_manifest),
            },
            "disk_lib_manifests": [
                {"path": path, "sha256": sha256_file(path)}
                for path in args.disk_lib_manifest
            ],
            "symbol_correction": args.symbol_correction,
            "namepool_correction": args.namepool_correction,
        },
        "limits": {
            "vm_dir_max": cap,
            "vm_codebuf": codebuf,
            "ext_code_limit": ext_code_limit,
            "max_symbols": max_sym,
            "namepool_bytes": namepool,
            "disk_file_max": disk_file_max,
        },
        "required_margins": {
            "load_entries": args.min_load_headroom,
            "post_align_entries": args.min_post_align_headroom,
            "ext_code_peak_bytes": min_ext_code_peak_headroom,
            "ext_code_post_bytes": args.min_ext_code_post_headroom,
            "symbols": args.min_symbol_headroom,
            "namepool_bytes": args.min_namepool_headroom,
        },
        "directory": {
            "resident_entries": resident,
            "disk_lib_entries": disk_lib_entries,
            "load_used": load_used,
            "load_headroom": cap - load_used,
            "post_align_used": post_align_used,
            "post_align_headroom": cap - post_align_used,
        },
        "codebuf": {
            "required": worst_codebuf_required,
            "headroom": codebuf - worst_codebuf_required,
            "worst_entry": worst_codebuf_name,
        },
        "ext_code": {
            "stages": ext_code_stages,
            "worst_peak_used": ext_code["peak_used"],
            "worst_peak_headroom": ext_code["peak_headroom"],
            "post_used": ext_code_post["post_used"],
            "post_headroom": ext_code_post["post_headroom"],
        },
        "symbols": {
            **symbols,
            "headroom": symbol_headroom,
        },
        "namepool": {
            "used": symbols["namepool_bytes"],
            "static_used": symbols["static_namepool_bytes"],
            "correction": symbols["namepool_correction"],
            "headroom": namepool_headroom,
        },
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )

    print(
        "workbench-disk-lib-budget: PASS resident=%d start=%d disk_lib=%d disk_libs=%d "
        "load_used=%d post_align=%d cap=%d headroom=%d post_headroom=%d "
        "codebuf=%d codebuf_required=%d codebuf_headroom=%d codebuf_worst=%s "
        "ext_code_peak_used=%d ext_code_peak_headroom=%d "
        "ext_code_post_used=%d ext_code_post_headroom=%d "
        "ext_code_reclaimed_bytes=%d ext_code_limit=%d "
        "disk_file_bytes=%d disk_file_max=%d disk_file_headroom=%d "
        "runtime_symbols=%d max_sym=%d symbol_headroom=%d "
        "runtime_namepool=%d namepool=%d namepool_headroom=%d "
        "disk_new_symbols=%d symbol_correction=%d namepool_correction=%d"
        % (
            resident,
            start,
            disk_lib,
            len(disk_lib_manifests),
            load_used,
            post_align_used,
            cap,
            cap - load_used,
            cap - post_align_used,
            codebuf,
            worst_codebuf_required,
            codebuf - worst_codebuf_required,
            worst_codebuf_name,
            ext_code["peak_used"],
            ext_code["peak_headroom"],
            ext_code_post["post_used"],
            ext_code_post["post_headroom"],
            sum(stage["reclaimed"] for stage in ext_code_stages),
            ext_code_limit,
            max(disk_lib_file_bytes),
            disk_file_max,
            disk_file_max - max(disk_lib_file_bytes),
            symbols["symbols"],
            max_sym,
            symbol_headroom,
            symbols["namepool_bytes"],
            namepool,
            namepool_headroom,
            symbols["disk_new_symbols"],
            symbols["symbol_correction"],
            symbols["namepool_correction"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
