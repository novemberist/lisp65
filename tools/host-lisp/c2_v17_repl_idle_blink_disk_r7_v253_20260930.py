#!/usr/bin/env python3
"""Replay c2_v17_repl_idle_blink_disk_r7_20260930.py in the pinned 2.5.2 source era (see era_replay_v253_20260930)."""
import era_replay_v253_20260930 as R

if __name__ == '__main__':
    R.run('c2_v17_repl_idle_blink_disk_r7_20260930.py', [['check']], 'c2_v17_repl_idle_blink_disk_r7_v253_20260930.py')
