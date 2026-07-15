#!/usr/bin/env python3
import sys
from pathlib import Path

from PIL import Image

ORACLE_BASE = 0x3000
EXPECTED_RGRAPHIC = bytes([1, 1, 0, 1, 1, 3, 0, 0, 0, 0, 0])


def fail(message: str) -> int:
    print(f"MEGA65 screen oracle check failed: {message}", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check-mega65-screen-oracle.py path/to/screenshot.png path/to/dump.mem", file=sys.stderr)
        return 2

    screenshot = Path(argv[1])
    dump = Path(argv[2])
    if not screenshot.is_file():
        return fail(f"missing screenshot: {screenshot}")
    if not dump.is_file():
        return fail(f"missing memory dump: {dump}")

    img = Image.open(screenshot).convert("RGB")
    if img.size != (800, 625):
        return fail(f"unexpected screenshot size: {img.size}")

    blue = 0
    black = 0
    white = 0
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = img.getpixel((x, y))
            if b > 180 and r < 40 and g < 40:
                blue += 1
            elif r < 40 and g < 40 and b < 40:
                black += 1
            elif r > 180 and g > 180 and b > 180:
                white += 1

    if blue < 220000:
        return fail(f"too few blue border/background pixels: {blue}")
    if black < 200000:
        return fail(f"too few black graphics-window pixels: {black}")
    if white > 100:
        return fail(f"unexpected white/noisy pixels in oracle screen: {white}")

    data = dump.read_bytes()
    if len(data) != 393216:
        return fail(f"unexpected memory dump size: {len(data)}")

    rgraphic = data[ORACLE_BASE:ORACLE_BASE + len(EXPECTED_RGRAPHIC)]
    if rgraphic != EXPECTED_RGRAPHIC:
        return fail(
            "unexpected RGRAPHIC oracle bytes at "
            f"${ORACLE_BASE:04x}: {list(rgraphic)}, expected {list(EXPECTED_RGRAPHIC)}"
        )

    fre4 = data[ORACLE_BASE + 11]
    fre5 = data[ORACLE_BASE + 12]

    print(
        "MEGA65 screen oracle check ok: "
        f"screenshot={img.size[0]}x{img.size[1]} blue={blue} black={black} white={white} "
        f"rgraphic={list(rgraphic)} fre4={fre4} fre5={fre5}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
