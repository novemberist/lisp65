"""Seed-2 object probe: the Seed-1 probe with the r2 decoder (member 1 withdrawn); output r3."""
import retained_callable_repair_object_probe as P

P.OUT = P.ROOT/'build/retained-callable-repair-object-probe-r3'
P.DECODER = P.ROOT/'config/retained-callable-repair-r2-native/includes/c2-stream-v2-decoder.c'

if __name__ == '__main__':
    P.main()
