#!/usr/bin/env python3
"""
Build Windows .ico from master icon.

Usage:
    1. python build_icons.py generate   - Scale master to all final PNGs
    2. (Hand-edit any icon_N.png files that need cleanup)
    3. python build_icons.py pack       - Pack PNGs into windows/airtype.ico
"""

import struct
import sys
from pathlib import Path

from PIL import Image

ASSETS_DIR = Path(__file__).parent
MASTER = ASSETS_DIR / "logo.png"
ICO_OUTPUT = ASSETS_DIR.parent / "windows" / "airtype.ico"
SIZES = [16, 20, 24, 32, 48, 64, 128, 256]


def generate():
    """Scale master icon to individual PNGs."""
    src = Image.open(MASTER).convert("RGBA")
    for s in SIZES:
        out = ASSETS_DIR / f"icon_{s}.png"
        src.resize((s, s), Image.LANCZOS).save(out)
        print(f"  {out.name}")
    print("Done. Hand-edit any sizes that need cleanup, then run: python build_icons.py pack")


def _rgba_to_ico_bmp(img: Image.Image) -> bytes:
    """Convert an RGBA PIL Image to ICO BMP format.

    ICO BMP = BITMAPINFOHEADER + BGRA pixels (bottom-up) + 1-bit AND mask.
    Tk's ICO parser only understands BMP frames, not PNG frames.
    """
    w, h = img.size
    pixels = img.load()

    and_row = ((w + 31) // 32) * 4          # 1-bit rows padded to 4 bytes
    and_size = and_row * h
    px_size = w * h * 4

    header = struct.pack(
        "<IiiHHIIiiII",
        40,             # biSize
        w,              # biWidth
        h * 2,          # biHeight (doubled — includes AND mask area)
        1,              # biPlanes
        32,             # biBitCount
        0,              # biCompression (BI_RGB)
        px_size + and_size,
        0, 0, 0, 0,    # pels/meter, clrUsed, clrImportant
    )

    # Pixel data: BGRA, bottom-up
    rows = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            rows.extend((b, g, r, a))

    return header + bytes(rows) + b"\x00" * and_size


def pack():
    """Pack individual PNGs into a multi-resolution .ico.

    Writes the ICO binary format directly because Pillow's ICO writer
    ignores append_images (broken as of Pillow 12.x).  Frames are stored
    as BMP (not PNG) so that Tk's built-in ICO parser can read every size.
    """
    frames: list[tuple[int, bytes]] = []
    for s in SIZES:
        path = ASSETS_DIR / f"icon_{s}.png"
        if not path.exists():
            print(f"Missing {path.name} - run 'generate' first")
            sys.exit(1)
        blob = _rgba_to_ico_bmp(Image.open(path).convert("RGBA"))
        frames.append((s, blob))
        print(f"  {path.name} ({s}x{s}, {len(blob)} bytes)")

    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)

    dir_size = 6 + count * 16
    offset = dir_size
    directory = b""
    for size, blob in frames:
        w = 0 if size == 256 else size
        directory += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)

    with open(ICO_OUTPUT, "wb") as f:
        f.write(header + directory)
        for _, blob in frames:
            f.write(blob)

    print(f"Saved {ICO_OUTPUT} ({count} frames, {offset} bytes)")


if __name__ == "__main__":
    commands = {
        "generate": generate,
        "pack": pack,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print("Usage: python build_icons.py [generate|pack]")
        sys.exit(1)

    commands[sys.argv[1]]()
