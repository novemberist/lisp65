"""2.5.2 post-Chunk-C Card-5 binding: v252 Card-5 source receipt plus the exact r7 product receipts.

Successor of c2_v251_card5_disk_r7_product_20260930 (immutable).
"""
import c2_v251_card5_disk_r7_product_20260930 as H0
import c2_v252_r1_card5 as H
import disk_r7_product_receipts_20260930 as P
import disk_r7_consumers_20260930 as S
# r2: binds the r2 Card-5 receipt (write-once; the r1 product receipt is superseded).
RECEIPT = 'config/c2-v252-r1-card5-product-receipt-r4.json'


def derive():
    return dict(source_card5=H0.verified(H.RECEIPT, H.derive()),
                product=H0.verified(str(P.RECEIPT.relative_to(S.ROOT)), P.derive()))


if __name__ == '__main__':
    S.finish('card5-r7-product-v252', derive, RECEIPT, H0,
             (__file__, H.__file__, H0.__file__, P.__file__, str(P.RECEIPT.relative_to(S.ROOT))))
