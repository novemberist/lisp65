#!/usr/bin/env python3
"""2.5.5 successor of the bound-artifact source-parity gate (generated row only).

The 2.5.4 key extension seam re-renders lib/ide-keymap-generated.lisp through
the dated entry point c2_v254_r1_keymap (%ide-prefix-command and
%ide-command-route gain the extension fallback).  The predecessor's generated
row runs c2_l_full_keymap_end_to_end_gate.py, whose renderer predates the seam,
so it can no longer reproduce the canonical generated output.  This successor
keeps every other row of the immutable predecessor (contract inventory,
mutations, carrier source binding, bound execution, product manifests,
absent-product semantics, rebind) and runs the keymap row through the 2.5.4
key-path successor c2_ide_exit_key_path_v254_r1.py, which executes the same
inherited end-to-end validation (BASE.validate with the host Lisp oracle and
its mutation set) against the 2.5.4 rendering plus the IDE exit checks.  The
native-function row is unchanged.  The predecessor tool stays immutable.
"""
import json
import subprocess
import sys

import c2_bound_artifact_source_parity as BOUND

KEYMAP_ROW = 'keymap-generated-source-and-consumer'
SUCCESSOR = 'tools/host-lisp/c2_ide_exit_key_path_v255_r1.py'


def generated_gate():
    commands = (
        ('native-function-generated-views',
         [sys.executable, 'tools/host-lisp/v2_native_function_registry.py', 'check']),
        (KEYMAP_ROW, [sys.executable, SUCCESSOR]),
    )
    rows = {}
    for name, command in commands:
        result = subprocess.run(command, cwd=BOUND.ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, check=False)
        BOUND.require(result.returncode == 0, f'{name} gate red:\n{result.stdout}')
        rows[name] = {'status': 'passed', 'terminal_line': result.stdout.strip().splitlines()[-1]}
    return rows


BOUND.generated_gate = generated_gate

if __name__ == '__main__':
    try:
        raise SystemExit(BOUND.main())
    except (BOUND.GateError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print('c2-bound-artifact-source-parity: FIRST RED: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
