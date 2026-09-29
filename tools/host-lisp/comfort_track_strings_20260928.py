"""Comfort replay with coherent fresh generated sources and suite declarations."""
import sys
import comfort_track_gate as H
from strings_scratch_20260928 import scratch, generated
if __name__=='__main__':
    with scratch() as root, generated(root):raise SystemExit(H.main(sys.argv))
