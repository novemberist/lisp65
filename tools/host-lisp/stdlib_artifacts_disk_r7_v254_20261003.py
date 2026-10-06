#!/usr/bin/env python3
"""Replay stdlib_artifacts_disk_r7_v253_20260930.py in the sealed 2.5.3 source era (see era_replay_v254_20261003)."""
import era_replay_v254_20261003 as R

if __name__ == '__main__':
    R.run('stdlib_artifacts_disk_r7_v253_20260930.py', [['check']], 'stdlib_artifacts_disk_r7_v254_20261003.py')
