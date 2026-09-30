"""Dated current r7 measurement; predecessor receipt remains immutable."""
import v11_function_metadata_ide_exit_20260928 as H
import disk_r7_consumers_20260930 as S
RECEIPT = 'config/v11-function-metadata-disk-r7-receipt-20260930.json'
HISTORY = {**H.HISTORY, **{'tools/host-lisp/v11_function_metadata_ide_exit_20260928.py': '08507ee8618d1dbee687da370a8a2cd8b94f7226b87574b63258a3f2d717e5b0', 'config/v11-function-metadata-receipt-ide-exit-r2-20260928.json': 'dfcdbd361fe71650335fc74151bcb17891f509bccf123ca693889a88a4fedc76'}}
def derive():
    S.S.history(HISTORY)
    with S.patch.object(H, 'RECEIPT', RECEIPT):
        current = H.derive()
    return dict(metadata=current, disk_r7=S.measure())

if __name__ == '__main__':
    S.finish('v11_function_metadata', derive, RECEIPT, H, (__file__, H.__file__))
