"""Current differential verdicts in a dated workspace; historical verdicts stay."""
import dialect_v2_system_runtime as H
import disk_r7_consumers_20260930 as S
H.OUTPUT = H.ROOT / 'build/bytecode/dialect-v2/system-runtime-disk-r7-20260930'
H.V1_BINARY = H.ROOT / 'build/equivalence-disk-r7-20260930/dialect-v1-equivalence-check'
H.V2_BINARY = H.ROOT / 'build/equivalence-disk-r7-20260930/dialect-v2-equivalence-check'
H.V1_BUILD = H.ROOT / 'build/equivalence-disk-r7-20260930/dialect-v1-build-receipt.json'
H.V2_BUILD = H.ROOT / 'build/equivalence-disk-r7-20260930/dialect-v2-build-receipt.json'
if __name__ == '__main__':
    S.source_controls()
    raise SystemExit(H.main())
