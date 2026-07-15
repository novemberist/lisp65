#!/usr/bin/env python3
"""Validate the runtime repro lifecycle registry and G5 resolution receipts."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from repl_screen_check import CheckError as ScreenCheckError
from repl_screen_check import PROMPT, _reconstruct_echo, _screen_content, check_latest_result


REQUIRED = {"name", "surface", "status", "expr", "expect", "reason"}
VALID_STATUS = {"known-open", "resolved-g5"}
VALID_SURFACE = {"native-repl", "mega65-hw", "xemu-mega65"}
REPL_FORMS_KEY = "native_repl_surface_forms"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
TREE_RE = COMMIT_RE
RECEIPT_FORMAT = "lisp65-runtime-g5-resolution-v1"
REQUIRED_STATES = {"after-persistence-remount", "after-long-ide-idex-search-repeat"}
CASE_FIXTURES = {
    "hw-higher-order-every-plusp-true": "h8e",
    "hw-higher-order-some-inline-lambda": "h8s",
}
STATE_ANCHORS = {
    "higher-order-remount-every": ("(m65d-remount)", "0"),
    "higher-order-remount-some": ("x", "t"),
    "higher-order-idex-some": ('(list (ide-buffer-point (car x)) (car (cdr x)))',
                               '((1 . 0) "found")'),
    "higher-order-idex-every": ("x", "3"),
}


class CheckError(ValueError):
    pass


def fail(msg):
    print("runtime-known-open-check: FAIL: %s" % msg, file=sys.stderr)
    return 1


def require(condition, message):
    if not condition:
        raise CheckError(message)


def exact_keys(value, keys, label):
    require(isinstance(value, dict), "%s must be an object" % label)
    actual = set(value)
    expected = set(keys)
    require(actual == expected, "%s keys differ: expected=%s actual=%s" %
            (label, sorted(expected), sorted(actual)))


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CheckError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)


def git_output(root, *args):
    try:
        return subprocess.check_output(
            ["git", "-C", str(root)] + list(args),
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CheckError("git provenance check failed: git %s" % " ".join(args)) from exc


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_root_for(path):
    for parent in (path.parent,) + tuple(path.parents):
        if (parent / ".git").exists():
            return parent
    raise CheckError("cannot locate repository root from %s" % path)


def repo_path(root, value, label, required_prefix=None):
    require(isinstance(value, str) and value, "%s must be a non-empty path" % label)
    relative = Path(value)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "%s must stay inside the repository" % label)
    if required_prefix is not None:
        require(relative.parts[:len(required_prefix)] == tuple(required_prefix),
                "%s must be below %s" % (label, "/".join(required_prefix)))
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        require(not cursor.is_symlink(), "%s cannot traverse a symlink: %s" % (label, value))
    path = root / relative
    require(path.is_file(), "%s is missing: %s" % (label, value))
    require(path.resolve().is_relative_to(root.resolve()),
            "%s resolves outside the repository: %s" % (label, value))
    return path


def evidence_file(base, entry, label, referenced):
    exact_keys(entry, {"file", "sha256"}, label)
    name = entry.get("file")
    digest = entry.get("sha256")
    require(isinstance(name, str) and name == Path(name).name,
            "%s.file must be a local file name" % label)
    require(isinstance(digest, str) and SHA256_RE.fullmatch(digest),
            "%s.sha256 must be a lowercase SHA-256" % label)
    path = base / name
    require(path.is_file(), "%s is missing: %s" % (label, path))
    require(not path.is_symlink(), "%s cannot be a symlink: %s" % (label, name))
    require(sha256_file(path) == digest, "%s SHA-256 mismatch: %s" % (label, name))
    require(name not in referenced, "evidence file referenced twice: %s" % name)
    referenced.add(name)
    return path


def parse_readback(path, expected_phase, manifest_sha):
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        require("=" in raw_line, "%s has a malformed readback line" % path)
        key, value = raw_line.split("=", 1)
        require(key and key not in values, "%s has a duplicate readback key %s" % (path, key))
        values[key] = value
    require(values.get("schema") == "lisp65-hw-ship-memory-readback-v2",
            "%s has the wrong readback schema" % path)
    require(values.get("phase") == expected_phase, "%s has the wrong readback phase" % path)
    require(values.get("manifest_sha256") == manifest_sha,
            "%s has the wrong manifest binding" % path)
    require(values.get("dry_run") == "0", "%s is only a dry-run" % path)
    require(values.get("status") == "PASS", "%s does not record PASS" % path)
    expected_keys = [key for key in values if key.endswith(".expected_sha256") or key.endswith(".expected_crc16")]
    require(expected_keys, "%s has no expected memory values" % path)
    for key in expected_keys:
        actual_key = key.replace(".expected_", ".actual_", 1)
        require(values.get(actual_key) == values[key], "%s differs at %s" % (path, key))
    return values


def expected_case_forms(case):
    expr = case["expr"]
    require(expr.count("'") == 1 and '"' not in expr and "\\" not in expr,
            "%s expression cannot be materialized exactly" % case["name"])
    prefix, suffix = expr.split("'", 1)
    fixture = case["fixture"]
    return [
        '(setq x "%s")' % prefix,
        '(setq x (string-append x (char->string 39) "%s"))' % suffix,
        f'(%ide-store-buffer (ide-make-buffer "{fixture}" (list x (string-append "(setq x " x ")"))))',
        '(save-buffer-to "%s" "%s")' % (fixture, fixture),
        '(load "%s")' % fixture,
        '(load "%s")' % fixture,
        "x",
    ]


def screen_segments(path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = [_screen_content(line) for line in raw.splitlines()]
    prompts = [index for index, line in enumerate(lines) if line.lstrip().startswith("lisp65>")]
    return lines, prompts


def screen_has_form_result(lines, prompts, expected_form, expected_result):
    for position, start in enumerate(prompts[:-1]):
        try:
            actual, echo_rows = _reconstruct_echo(lines, start, expected_form)
        except ScreenCheckError:
            continue
        if actual != expected_form:
            continue
        end = prompts[position + 1]
        results = [line.strip() for line in lines[start + echo_rows:end] if line.strip()]
        if results and results[-1] == expected_result:
            return True
    return False


def validate_phase_transcript(path, expected_forms, expected_result, phase_id, label):
    lines, prompts = screen_segments(path)
    require(len(prompts) >= len(expected_forms) + 1,
            "%s does not show the complete seven-form phase" % label)
    phase_prompts = prompts[-(len(expected_forms) + 1):]
    require(lines[phase_prompts[-1]].strip() == PROMPT.rstrip(),
            "%s does not end at a clean prompt" % label)
    for i, expected_form in enumerate(expected_forms):
        start = phase_prompts[i]
        end = phase_prompts[i + 1]
        try:
            actual, echo_rows = _reconstruct_echo(lines, start, expected_form)
        except ScreenCheckError as exc:
            raise CheckError("%s form %d echo is malformed: %s" % (label, i + 1, exc.message)) from exc
        require(actual == expected_form,
                "%s form %d differs: expected=%r actual=%r" % (label, i + 1, expected_form, actual))
        visible = [line.strip() for line in lines[start + echo_rows:end] if line.strip()]
        require(visible and not any(line.startswith("*** ") for line in visible),
                "%s form %d has no result or reports an error" % (label, i + 1))
    anchor_form, anchor_result = STATE_ANCHORS[phase_id]
    require(screen_has_form_result(lines, prompts, anchor_form, anchor_result),
            "%s lacks its product-state anchor %r => %r" % (label, anchor_form, anchor_result))
    try:
        check_latest_result(path, expected_forms[-1], expected_result)
    except ScreenCheckError as exc:
        raise CheckError("%s failed repl_screen_check: %s" % (label, exc.message)) from exc


def validate_receipt(path, registry_cases):
    data = load_json(path)
    exact_keys(data, {"schema", "id", "scope", "gate", "dry_run", "result", "completed_at",
                       "hardware", "ship", "execution", "source_transport", "supporting_evidence", "cases"}, path)
    require(data.get("schema") == RECEIPT_FORMAT,
            "%s has bad receipt schema %r" % (path, data.get("schema")))
    require(data.get("id") == "ap8.1-g5-78083d6", "%s has the wrong receipt id" % path)
    require(data.get("scope") == "ap8.1-higher-order", "%s overstates its evidence scope" % path)
    require(data.get("gate") == "G5" and data.get("dry_run") is False and data.get("result") == "pass",
            "%s is not a passing live G5 receipt" % path)
    require(data.get("completed_at") == "2026-07-11" and data.get("hardware") == "MEGA65",
            "%s has the wrong completion date or hardware surface" % path)
    base = path.parent
    referenced = set()

    ship = data.get("ship")
    exact_keys(ship, {"manifest", "manifest_sha256", "manifest_format", "manifest_status",
                      "source_commit", "source_tree", "source_dirty"}, "%s.ship" % path)
    manifest_path = evidence_file(base, {
        "file": ship.get("manifest"),
        "sha256": ship.get("manifest_sha256"),
    }, "%s.ship.manifest" % path, referenced)
    require(COMMIT_RE.fullmatch(str(ship.get("source_commit", ""))),
            "%s ship source commit must be a full commit id" % path)
    require(TREE_RE.fullmatch(str(ship.get("source_tree", ""))),
            "%s ship source tree must be a full tree id" % path)
    require(ship.get("source_dirty") is False, "%s ship source must be clean" % path)
    manifest = load_json(manifest_path)
    require(manifest.get("manifest_format") == ship.get("manifest_format"),
            "%s manifest format binding mismatch" % path)
    require(manifest.get("status") == ship.get("manifest_status"),
            "%s manifest status binding mismatch" % path)
    source = manifest.get("source", {})
    require(source.get("commit") == ship.get("source_commit"),
            "%s manifest source commit binding mismatch" % path)
    require(source.get("tree") == ship.get("source_tree"),
            "%s manifest source tree binding mismatch" % path)
    require(source.get("dirty") is False, "%s manifest records a dirty source" % path)
    repo_root = repo_root_for(path)
    commit = ship["source_commit"]
    git_output(repo_root, "cat-file", "-e", "%s^{commit}" % commit)
    require(git_output(repo_root, "rev-parse", "%s^{tree}" % commit) == ship["source_tree"],
            "%s source tree does not match the Git commit" % path)
    require(ship.get("manifest_format") == "lisp65-workbench-ship-v5" and
            manifest.get("manifest_format") == "lisp65-workbench-ship-v5",
            "%s must bind Ship-v5" % path)
    require(ship.get("manifest_status") == "g2-verified-candidate" and
            manifest.get("status") == "g2-verified-candidate",
            "%s must bind a G2-verified candidate" % path)
    require(manifest.get("product") == "lisp65-workbench",
            "%s manifest is not the Workbench product" % path)
    require(manifest.get("profile") == "mvp-vm-stdlib-einsuite-core-workbench",
            "%s manifest is not the canonical Workbench profile" % path)
    gates = manifest.get("gates", {})
    require(all(gates.get(gate) == "pass" for gate in ("G0", "G1", "G2")),
            "%s manifest does not bind passing G0-G2" % path)

    execution = data.get("execution")
    exact_keys(execution, {"primary_target", "verified_harness", "workbench_ux_result",
                           "higher_order_phases_result", "full_check_hardware_exit_zero",
                           "note"}, "%s.execution" % path)
    require(execution.get("primary_target") == "make check-hardware",
            "%s must name make check-hardware as the primary target" % path)
    harness = repo_path(repo_root_for(path), execution.get("verified_harness"),
                        "%s.execution.verified_harness" % path)
    require(harness.name == "hw-workbench-ux-smoke.sh",
            "%s binds the wrong verified UX harness" % path)
    for key in ("workbench_ux_result", "higher_order_phases_result"):
        require(execution.get(key) == "pass", "%s.execution.%s must be pass" % (path, key))
    require(execution.get("full_check_hardware_exit_zero") is False,
            "%s must not overstate the interrupted aggregate as exit-zero" % path)
    require(isinstance(execution.get("note"), str) and execution["note"].strip(),
            "%s must retain its execution caveat" % path)

    transport = data.get("source_transport")
    exact_keys(transport, {"method", "loads_per_state", "result_form", "allocation_note"},
               "%s.source_transport" % path)
    require(transport.get("method") == "materialize-exact-apostrophe-source-via-char-code-39-save-and-load",
            "%s must bind exact apostrophe-source materialization" % path)
    require(transport.get("loads_per_state") == 2,
            "%s must execute each materialized source twice per state" % path)
    require(transport.get("result_form") == "x", "%s must bind the final x oracle" % path)
    require(isinstance(transport.get("allocation_note"), str) and transport["allocation_note"].strip(),
            "%s must retain the reader-allocation caveat" % path)

    supporting = data.get("supporting_evidence")
    require(isinstance(supporting, list) and supporting,
            "%s.supporting_evidence must be non-empty" % path)
    supporting_paths = []
    for i, entry in enumerate(supporting):
        support_path = evidence_file(base, entry, "%s.supporting_evidence[%d]" % (path, i), referenced)
        supporting_paths.append(support_path)
    manifest_sha = ship["manifest_sha256"]
    require(all(manifest_sha in item.read_text(encoding="utf-8") for item in supporting_paths),
            "%s supporting evidence does not consistently bind the ship manifest" % path)
    require(len(supporting_paths) == 3, "%s must bind memory receipt and two readbacks" % path)
    memory_receipts = [item for item in supporting_paths if item.suffix == ".json"]
    require(len(memory_receipts) == 1, "%s must bind exactly one memory receipt" % path)
    memory_receipt = load_json(memory_receipts[0])
    exact_keys(memory_receipt, {"schema", "dry_run", "manifest_sha256", "island_sha256"},
               "%s memory receipt" % path)
    require(memory_receipt.get("schema") == "lisp65-hw-ship-memory-receipt-v2" and
            memory_receipt.get("dry_run") is False and
            memory_receipt.get("manifest_sha256") == manifest_sha,
            "%s memory receipt is not a live binding" % path)
    require(SHA256_RE.fullmatch(str(memory_receipt.get("island_sha256", ""))),
            "%s memory receipt has an invalid island SHA-256" % path)
    readbacks = [item for item in supporting_paths if item.suffix == ".txt"]
    require(len(readbacks) == 2, "%s must bind exactly two memory readbacks" % path)
    readback_values = {}
    for phase in ("staged", "post-reset"):
        matches = [item for item in readbacks if phase in item.name]
        require(len(matches) == 1, "%s must bind one %s readback" % (path, phase))
        readback_values[phase] = parse_readback(matches[0], phase, manifest_sha)
    require(readback_values["post-reset"].get("resident-island.actual_sha256") ==
            memory_receipt["island_sha256"], "%s island receipt/readback binding mismatch" % path)
    artifacts = {item.get("id"): item.get("sha256") for item in manifest.get("artifacts", [])}
    require(readback_values["staged"].get("bank5-preload.actual_sha256") ==
            artifacts.get("workbench-stdlib-blob"), "%s Bank-5 readback/manifest mismatch" % path)
    require(readback_values["staged"].get("attic-catalog.actual_sha256") ==
            artifacts.get("workbench-runtime-overlays"), "%s Attic readback/manifest mismatch" % path)
    require(readback_values["post-reset"].get("attic-catalog.actual_sha256") ==
            artifacts.get("workbench-runtime-overlays"), "%s post-reset Attic/manifest mismatch" % path)

    receipt_cases = data.get("cases")
    require(isinstance(receipt_cases, list) and receipt_cases,
            "%s.cases must be a non-empty list" % path)
    by_name = {}
    state_orders = {state: [] for state in REQUIRED_STATES}
    phase_sequence = {}
    for case in receipt_cases:
        exact_keys(case, {"name", "fixture", "expr", "expect", "phases"}, "%s receipt case" % path)
        name = case.get("name")
        require(isinstance(name, str) and name not in by_name,
                "%s has an invalid or duplicate receipt case name" % path)
        by_name[name] = case
        require(case.get("fixture") == CASE_FIXTURES.get(name),
                "%s has the wrong fixture id" % name)
        expected_forms = expected_case_forms(case)
        registry_case = registry_cases.get(name)
        require(registry_case is not None, "%s receipt has unregistered case %s" % (path, name))
        require(case.get("expr") == registry_case["expr"], "%s expression binding mismatch" % name)
        require(case.get("expect") == registry_case["expect"], "%s result binding mismatch" % name)
        phases = case.get("phases")
        require(isinstance(phases, list) and len(phases) == 2,
                "%s must have exactly two G5 phases" % name)
        phase_ids = set()
        states = set()
        for i, phase in enumerate(phases):
            label = "%s phase %d" % (name, i)
            exact_keys(phase, {"id", "state", "order", "loads", "forms", "transcript"}, label)
            phase_id = phase.get("id")
            state = phase.get("state")
            require(isinstance(phase_id, str) and phase_id not in phase_ids,
                    "%s has an invalid or duplicate id" % label)
            require(state in REQUIRED_STATES and state not in states,
                    "%s has an invalid or duplicate product state" % label)
            phase_ids.add(phase_id)
            states.add(state)
            require(phase.get("loads") == transport["loads_per_state"],
                    "%s load count does not match the transport contract" % label)
            order = phase.get("order")
            require(order in (1, 2), "%s order must be 1 or 2" % label)
            state_orders[state].append(order)
            require((state, order) not in phase_sequence, "%s duplicates a state/order position" % label)
            phase_sequence[(state, order)] = phase_id
            forms_path = evidence_file(base, phase.get("forms"), label + ".forms", referenced)
            transcript_path = evidence_file(base, phase.get("transcript"), label + ".transcript", referenced)
            forms = forms_path.read_text(encoding="utf-8")
            actual_forms = [line for line in forms.splitlines() if line]
            require(actual_forms == expected_forms,
                    "%s forms differ from the exact case materialization" % label)
            transcript = transcript_path.read_text(encoding="utf-8")
            require(case["expr"] in transcript, "%s transcript lacks the exact source" % label)
            validate_phase_transcript(transcript_path, expected_forms, case["expect"], phase_id, label)
        require(states == REQUIRED_STATES, "%s does not cover both required product states" % name)
        required_ids = set(registry_case["resolution"].get("phase_ids", []))
        require(phase_ids == required_ids, "%s phase ids differ from the registry" % name)

    require(set(by_name) == set(registry_cases),
            "%s receipt cases differ from its registry references" % path)
    require(all(sorted(orders) == [1, 2] for orders in state_orders.values()),
            "%s must run the two cases in opposite complete orders across both states" % path)
    require(phase_sequence == {
        ("after-persistence-remount", 1): "higher-order-remount-every",
        ("after-persistence-remount", 2): "higher-order-remount-some",
        ("after-long-ide-idex-search-repeat", 1): "higher-order-idex-some",
        ("after-long-ide-idex-search-repeat", 2): "higher-order-idex-every",
    }, "%s phase sequence differs from the approved reciprocal order" % path)
    actual_evidence = {item.name for item in base.iterdir() if item.is_file() and item.name != path.name}
    require(actual_evidence == referenced,
            "%s evidence inventory mismatch: referenced=%s actual=%s" %
            (path, sorted(referenced), sorted(actual_evidence)))


def validate_registry(path, quiet=False):
    data = load_json(path)
    exact_keys(data, {"format", "description", "historical_diagnostic_harness",
                      "native_repl_surface_handoff", "native_repl_surface_forms",
                      "resolution_receipts", "cases"}, "registry")
    require(data.get("format") == "lisp65-runtime-known-open-v2",
            "bad format: %r" % data.get("format"))
    cases = data.get("cases")
    require(isinstance(cases, list) and cases, "cases must be a non-empty list")
    root = repo_root_for(path)
    exact_keys(data.get("historical_diagnostic_harness"),
               {"target", "prg_target", "embedded_suite", "flags", "note"},
               "historical_diagnostic_harness")

    names = set()
    cases_by_name = {}
    surfaces = {}
    repl_surface_forms = set()
    receipt_cases = {}
    for i, case in enumerate(cases):
        require(isinstance(case, dict), "case %d is not an object" % i)
        missing = sorted(REQUIRED - set(case))
        require(not missing, "%s missing %s" % (case.get("name", "case %d" % i), ", ".join(missing)))
        name = case["name"]
        require(name not in names, "duplicate case name: %s" % name)
        names.add(name)
        cases_by_name[name] = case
        require(case["status"] in VALID_STATUS, "%s has invalid status %r" % (name, case["status"]))
        require(case["surface"] in VALID_SURFACE, "%s has invalid surface %r" % (name, case["surface"]))
        for key in ("expr", "expect", "reason"):
            require(isinstance(case[key], str) and case[key].strip(), "%s has empty %s" % (name, key))
        if case["surface"] == "native-repl":
            surface_form = case.get("surface_form")
            require(isinstance(surface_form, str) and surface_form.strip(),
                    "%s native-repl case must name surface_form" % name)
            repl_surface_forms.add(surface_form)
        if case["status"] == "known-open":
            exact_keys(case, REQUIRED, name)
            require("resolution" not in case, "%s known-open case cannot have a resolution" % name)
        else:
            exact_keys(case, REQUIRED | {"resolution"}, name)
            resolution = case.get("resolution")
            exact_keys(resolution, {"receipt", "receipt_case", "phase_ids"}, "%s.resolution" % name)
            require(resolution.get("receipt_case") == name,
                    "%s receipt_case must equal the case name" % name)
            phase_ids = resolution.get("phase_ids")
            require(isinstance(phase_ids, list) and len(phase_ids) == 2 and len(set(phase_ids)) == 2,
                    "%s must bind two unique phase ids" % name)
            receipt = resolution.get("receipt")
            repo_path(root, receipt, "%s resolution receipt" % name,
                      ("tests", "bytecode", "runtime", "evidence"))
            receipt_cases.setdefault(receipt, {})[name] = case
        surfaces[case["surface"]] = surfaces.get(case["surface"], 0) + 1

    form_entries = data.get(REPL_FORMS_KEY, [])
    require(isinstance(form_entries, list), "%s must be a list" % REPL_FORMS_KEY)
    require(not repl_surface_forms or form_entries,
            "%s must be non-empty when native-repl cases exist" % REPL_FORMS_KEY)
    listed_forms = set()
    for i, entry in enumerate(form_entries):
        require(isinstance(entry, dict), "%s[%d] is not an object" % (REPL_FORMS_KEY, i))
        form = entry.get("form")
        require(isinstance(form, str) and form.strip(), "%s[%d].form must be non-empty" % (REPL_FORMS_KEY, i))
        require(form not in listed_forms, "duplicate native REPL surface form: %s" % form)
        listed_forms.add(form)
        require(entry.get("status") in VALID_STATUS, "%s has invalid status" % form)
        entry_cases = entry.get("cases")
        require(isinstance(entry_cases, list) and entry_cases, "%s must list at least one repro case" % form)
        for case_name in entry_cases:
            case = cases_by_name.get(case_name)
            require(case is not None and case["surface"] == "native-repl" and case.get("surface_form") == form,
                    "%s has invalid case reference %s" % (form, case_name))
    require(listed_forms == repl_surface_forms,
            "native REPL surface form list %s does not match cases %s" %
            (sorted(listed_forms), sorted(repl_surface_forms)))

    receipts = data.get("resolution_receipts")
    require(isinstance(receipts, list), "resolution_receipts must be a list")
    receipt_index = {}
    for i, entry in enumerate(receipts):
        exact_keys(entry, {"path", "sha256"}, "resolution_receipts[%d]" % i)
        receipt_path = entry.get("path")
        digest = entry.get("sha256")
        require(receipt_path not in receipt_index, "duplicate resolution receipt: %s" % receipt_path)
        require(isinstance(digest, str) and SHA256_RE.fullmatch(digest),
                "%s receipt SHA-256 is invalid" % receipt_path)
        resolved = repo_path(root, receipt_path, "resolution receipt",
                             ("tests", "bytecode", "runtime", "evidence"))
        require(sha256_file(resolved) == digest, "resolution receipt SHA-256 mismatch: %s" % receipt_path)
        receipt_index[receipt_path] = resolved
    require(set(receipt_index) == set(receipt_cases),
            "resolution receipt index differs from resolved case references")
    for receipt_path, resolved in receipt_index.items():
        validate_receipt(resolved, receipt_cases[receipt_path])

    summary = " ".join("%s=%d" % item for item in sorted(surfaces.items()))
    status_summary = " ".join("%s=%d" % (status, sum(c["status"] == status for c in cases))
                              for status in sorted(VALID_STATUS))
    if not quiet:
        print("runtime-known-open-check: PASS cases=%d receipts=%d repl_forms=%d %s %s" %
              (len(cases), len(receipt_index), len(listed_forms), status_summary, summary))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: runtime_known_open_check.py path/to/known-open.json", file=sys.stderr)
        return 2
    path = Path(argv[0]).resolve()
    try:
        validate_registry(path)
    except (CheckError, json.JSONDecodeError, OSError) as exc:
        return fail(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
