"""Strings successor; replay predecessor against exact pre-string inputs."""
import c2_v251_public_authority_walks_20260928 as H
import strings_successor_r2_20260928 as S
RECEIPT='config/c2-v251-public-authority-receipt-strings-r2-20260928.json'
HISTORY={'tools/host-lisp/c2_v251_public_authority_walks_20260928.py': '98f1272fb76a0fabbdb9c3d514a8f013ef2984bc203aec1d735f16c1839bdae7', 'config/c2-v251-public-authority-receipt-walks-20260928.json': 'c41866855dbece9e42de4ca1cb6e6037feb6da4ab71e771981f3b67edeca1ef9', 'tools/host-lisp/c2_v251_public_authority_strings_20260928.py': '5c04732889f3aa8d810fbe6b13dd5387c1762b579cd21ac88128ec113c9569c6', 'config/c2-v251-public-authority-receipt-strings-20260928.json': '535466c20199b157c369e76b720e835e9c6261c0cef292b1481bf854bd033555'}
def derive():
    with S.predecessor_world(): inherited=H.derive()
    return dict(inherited=inherited,live_strings=S.live())
if __name__=='__main__':
    S.finish('c2_v251_public_authority',derive,RECEIPT,HISTORY,(__file__,H.__file__,'tests/bytecode/libs/p0-repl-comfort-v250.json'))
