# Host-only package verifier for profile-bound overlay prototypes.

.PHONY: overlay-package-selftest

overlay-package-selftest:
	python3 tools/host-lisp/overlay_package.py selftest
