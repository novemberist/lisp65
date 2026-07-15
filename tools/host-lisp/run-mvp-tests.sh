#!/bin/sh
# Fast MVP host checks for the new lisp65 codebase.
#
# This intentionally combines:
# - the CL-near eval/Prelude oracles in lib/tests;
# - the String-ABI and Stdlib conformance oracles for Lane L.
# Reader conformance is owned by the semantic-contract registry.  The salvaged
# LISP64 baseline is an explicit reference target, not a lisp65 host contract.
set -eu
cd "$(dirname "$0")/../.."

python3 tools/host-lisp/mvp_cl_eval_oracle.py
python3 tools/host-lisp/mvp_prelude_surface_oracle.py
python3 tools/host-lisp/mvp_prelude_macro_oracle.py
python3 tools/host-lisp/mvp_prelude_source_oracle.py
python3 tools/host-lisp/mvp_prelude_m1_macro_oracle.py
python3 tools/host-lisp/mvp_prelude_m1_eval_oracle.py
python3 tools/host-lisp/string_abi_oracle.py
python3 tools/host-lisp/check_ship_readiness.py --selftest
python3 tools/host-lisp/check_ship_artifacts.py --selftest
python3 tools/host-lisp/stdlib_conformance_plan_oracle.py
python3 tools/host-lisp/stdlib_string_eval_oracle.py
python3 tools/host-lisp/stdlib_sequence_eval_oracle.py
python3 tools/host-lisp/stdlib_math_eval_oracle.py
python3 tools/host-lisp/stdlib_plist_eval_oracle.py
python3 tools/host-lisp/stdlib_format_eval_oracle.py
python3 tools/host-lisp/stdlib_control_eval_oracle.py
