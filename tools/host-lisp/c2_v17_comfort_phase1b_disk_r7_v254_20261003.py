#!/usr/bin/env python3
"""Replay c2_v17_comfort_phase1b_disk_r7_v253_20260930.py in the sealed 2.5.3 source era (see era_replay_v254_20261003)."""
import era_replay_v254_20261003 as R

if __name__ == '__main__':
    R.run('c2_v17_comfort_phase1b_disk_r7_v253_20260930.py', [['qualification-check']], 'c2_v17_comfort_phase1b_disk_r7_v254_20261003.py')
