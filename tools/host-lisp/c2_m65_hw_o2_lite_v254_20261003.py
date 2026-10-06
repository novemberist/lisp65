#!/usr/bin/env python3
"""Run c2_m65_hw_o2_lite_20260929.py live under the 2.5.4 O2-lite source pin (see era_replay_v254_20261003.run_live
and o2_lite_consumers_v254_20261003); the consumer itself is unchanged."""
import era_replay_v254_20261003 as R

if __name__ == '__main__':
    R.run_live('c2_m65_hw_o2_lite_20260929.py', None, 'c2_m65_hw_o2_lite_v254_20261003.py')
