"""2.5.5 post-Chunk-C Card-5 binding: v255 Card-5 source receipt plus the exact r7 product receipts.

Successor of c2_v254_r1_card5_product (immutable, receipt r5; it binds the 2.5.4 Card-5 source half, whose route
block-26-build-integrity-check moved to c2_v255_r1_card5 with the 2.5.5 source candidate).  Nothing else changes:
the r7 product receipts witness the 2.5.2 product build and are replayed in the pinned 2.5.2 source era inside the
sealed 2.5.3 world (era_replay_v254_20261003); the host compiler row of that build is accepted under the
historical host pin rule, here through its 2.5.5 successor module; the source Card-5 half binds the live tree
through c2_v255_r1_card5.
"""
import c2_v251_card5_disk_r7_product_20260930 as H0
import c2_v255_r1_card5 as H
import disk_r7_product_receipts_20260930 as P
import disk_r7_consumers_20260930 as S
import disk_r7_product_receipts_v253_20260930 as W
import era_replay_v254_20261003 as R
import historical_host_pin_v255_20261007 as HOST
import strings_seed_producer as BOUND
RECEIPT = 'config/c2-v255-r1-card5-product-receipt-r3.json'  # r3: binds the card5 r3 receipt (ship-time doc gates r2; r2 is committed)


def derive():
    source = H0.verified(H.RECEIPT, H.derive())
    with R.world(), W.era() as reads, HOST.checked_world('2.5.2', BOUND):
        product = H0.verified(str(P.RECEIPT.relative_to(S.ROOT)), P.derive())
    S.require(reads, 'historical product receipts consumed no host sources')
    return dict(source_card5=source, product=product)


if __name__ == '__main__':
    R.V.route_children()
    R.pin_disk_r7_source_controls()
    S.finish('card5-r7-product-v255', derive, RECEIPT, H0,
             (__file__, H.__file__, H0.__file__, P.__file__, W.__file__, R.__file__, HOST.__file__,
              str(P.RECEIPT.relative_to(S.ROOT))))
