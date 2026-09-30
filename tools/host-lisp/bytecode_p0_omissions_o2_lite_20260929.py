"""Dated suite routing; all inherited gate controls remain enabled."""
import runpy
import o2_lite_consumers_20260929 as S
if __name__=="__main__":
    S.controls()
    with S.suites():runpy.run_module('bytecode_p0_omissions_strings_20260928',run_name="__main__")
