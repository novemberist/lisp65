#!/usr/bin/env python3
"""Replay disk_r7_consumer_mutations_20260930.py in the pinned 2.5.2 source era (see era_replay_v253_20260930)."""
import era_replay_v253_20260930 as R

if __name__ == '__main__':
    R.run('disk_r7_consumer_mutations_20260930.py', [['check']], 'disk_r7_consumer_mutations_v253_20260930.py')
