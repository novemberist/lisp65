"""Card L Option-A successor: only resolver entry point changes.
All inherited prior-append witnesses and mutations execute unchanged.
"""
import c2_require_prior_append_option_a_gate as P
P.SOURCE_GATE=P.ROOT/'tools/host-lisp/card_l_resolver_20260925.py'
# The original gate calls the resolver with no action argument.
if __name__=='__main__':raise SystemExit(P.main())
