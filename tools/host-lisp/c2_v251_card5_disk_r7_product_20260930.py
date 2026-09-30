"""Post-Chunk-C Card-5 binding of source and exact r7 product receipts."""
import c2_v251_card5_disk_r7_20260930 as H
import disk_r7_product_receipts_20260930 as P
import disk_r7_consumers_20260930 as S
RECEIPT = 'config/c2-v251-card5-disk-r7-product-receipt-20260930.json'

def verified(receipt, current):
    value = S.json.loads((S.ROOT / receipt).read_bytes())
    for row in value['inputs']:
        S.require(S.S.bind(row['path']) == row, 'post-C Card-5 input drift')
    S.require(value['current'] == current, 'post-C Card-5 measurement drift')
    return S.S.bind(receipt)

def derive():
    return dict(source_card5=verified(H.RECEIPT, H.derive()),
                product=verified(str(P.RECEIPT.relative_to(S.ROOT)), P.derive()))

if __name__ == '__main__':
    S.finish('card5-r7-product', derive, RECEIPT, H,
             (__file__, H.__file__, P.__file__, str(P.RECEIPT.relative_to(S.ROOT))))
