"""2.5.3 post-Chunk-C Card-5 binding: v253 Card-5 source receipt plus the exact r7 product receipts.

Successor of c2_v252_r1_card5_product (immutable, receipt r4). The r7 product
receipts witness the 2.5.2 product build; they bind Lisp sources (for example
lib/domain-tier1.lisp) as that build consumed them. The 2.5.3 candidate changes
those sources on purpose, so the product half is replayed in the pinned 2.5.2
source era (same commit as the other era-scoped 2.5.3 successors); the source
Card-5 half binds the live tree.
"""
import c2_v251_card5_disk_r7_product_20260930 as H0
import c2_v253_r1_card5 as H
import disk_r7_product_receipts_20260930 as P
import disk_r7_consumers_20260930 as S
import disk_r7_product_receipts_v253_20260930 as W
import era_replay_v253_20260930 as R
RECEIPT = 'config/c2-v253-r1-card5-product-receipt-r10.json'  # r10: binds the card5 r10 receipt (2.5.3 ship-time doc gates r3; r9 is committed)


def derive():
    source = H0.verified(H.RECEIPT, H.derive())
    with W.era() as reads:
        product = H0.verified(str(P.RECEIPT.relative_to(S.ROOT)), P.derive())
    S.require(reads, 'historical product receipts consumed no host sources')
    return dict(source_card5=source, product=product)


if __name__ == '__main__':
    R.pin_disk_r7_source_controls()
    S.finish('card5-r7-product-v253', derive, RECEIPT, H0,
             (__file__, H.__file__, H0.__file__, P.__file__, W.__file__, str(P.RECEIPT.relative_to(S.ROOT))))
