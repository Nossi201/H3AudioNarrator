#!/usr/bin/env python3
"""
make_mybtn_def.py
Generuje MYBTN.DEF (H3 Type-71) z normal.png i hover.png.
Grupa 0 = normal  (8 klatek, po jednej na gracza).
Grupa 1 = hover   (8 klatek, po jednej na gracza).
H3 wybiera klatkę przez ColorDefToPlayer(playerIndex).
"""

import struct, os, colorsys
from PIL import Image

NORMAL_PNG = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3Plugins\normal.png"
HOVER_PNG  = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3Plugins\hover.png"
OUT_DEF    = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3Plugins\MYBTN.DEF"

# Kąty barwy (hue) dla 8 graczy H3: Red, Blue, Tan, Green, Orange, Purple, Teal, Pink
PLAYER_HUES = [0, 215, 35, 120, 25, 280, 175, 330]
# Barwa tła oryginalnego obrazu (fioletowy ≈ 280°)
SRC_HUE = 280.0


# ---------------------------------------------------------------------------
# Obrót barwy
# ---------------------------------------------------------------------------

def rotate_hue(img: Image.Image, target_deg: float, src_deg: float) -> Image.Image:
    """Obraca hue obrazu RGBA z src_deg na target_deg.
    Piksele o nasyceniu < 0.08 (szare/czarne/białe) pozostają bez zmian."""
    delta = ((target_deg - src_deg) % 360) / 360.0
    if abs(delta) < 1e-9:
        return img.copy()
    out = img.copy()
    pix = list(out.getdata())
    new_pix = []
    for r, g, b, a in pix:
        if a < 128:
            new_pix.append((r, g, b, a))
        else:
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if s > 0.08:
                h = (h + delta) % 1.0
            nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
            new_pix.append((round(nr * 255), round(ng * 255), round(nb * 255), a))
    out.putdata(new_pix)
    return out


# ---------------------------------------------------------------------------
# Budowanie palety i indeksowanie klatek
# ---------------------------------------------------------------------------

def build_indexed_frames(all_frames, w, h):
    """
    Tworzy wspólną 256-kolorową paletę i konwertuje wszystkie klatki na listy indeksów.
    Indeksy 0-7: transparent/shadow (H3 traktuje je jako przezroczyste).
    Indeksy 8-255: 248 kolorów z kwantyzacji.
    """
    print("  Budowanie palety (kwantyzacja)...")
    combined = Image.new('RGB', (w * len(all_frames), h))
    for i, f in enumerate(all_frames):
        combined.paste(f.convert('RGB'), (i * w, 0))
    quant = combined.quantize(colors=248, dither=0)
    pal_flat = quant.getpalette()[:248 * 3]

    # palette_rgb[0..7] = transparent; [8..255] = kolory
    palette_rgb = [(0, 0, 0)] * 8
    for i in range(248):
        palette_rgb.append((pal_flat[i * 3], pal_flat[i * 3 + 1], pal_flat[i * 3 + 2]))
    while len(palette_rgb) < 256:
        palette_rgb.append((0, 0, 0))

    # Szybkie wyszukiwanie przez cache
    color_cache = {}

    def nearest_idx(r, g, b):
        best = 8
        best_d = 999_999_999
        for i in range(8, 256):
            pr, pg, pb = palette_rgb[i]
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_d = d
                best = i
                if d == 0:
                    break
        return best

    print("  Indeksowanie klatek...")
    frames_indexed = []
    for fi, f in enumerate(all_frames):
        pixels = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = f.getpixel((x, y))
                if a < 128:
                    pixels.append(0)
                else:
                    key = (r, g, b)
                    if key not in color_cache:
                        color_cache[key] = nearest_idx(r, g, b)
                    pixels.append(color_cache[key])
        frames_indexed.append(pixels)
        print(f"    Klatka {fi:2d}: {len([p for p in pixels if p == 0]):4d} transparent, "
              f"{len([p for p in pixels if p >= 8]):4d} opaque")

    return palette_rgb, frames_indexed


# ---------------------------------------------------------------------------
# Zapis DEF
# ---------------------------------------------------------------------------

def write_def(path, frames_g0, frames_g1, palette_rgb, w, h):
    """
    Zapisuje plik H3 Type-71 DEF.
    Format zgodny z make_sprites.py / iOKAY.def.
    Compression = 0 (raw pixels, bez kompresji).
    """
    def u32(v):
        return struct.pack('<I', v)

    def fname(s):
        return s.encode('ascii').ljust(13, b'\x00')[:13]

    def frame_block(pixels):
        blk = bytearray()
        blk += u32(w * h)  # dataSize (raw: w*h bajtów)
        blk += u32(0)      # compression = 0
        blk += u32(w)      # fullWidth
        blk += u32(h)      # fullHeight
        blk += u32(w)      # frameWidth
        blk += u32(h)      # frameHeight
        blk += u32(0)      # xOffset = 0
        blk += u32(0)      # yOffset = 0
        blk += bytes(pixels[:w * h])
        return blk

    NUM_FRAMES = 8   # per group
    NUM_GROUPS = 2

    HDR_SIZE  = 4 * 4 + 256 * 3                             # 16 + 768 = 784
    GRP_SIZE  = 4 * 4 + 13 * NUM_FRAMES + 4 * NUM_FRAMES   # 16 + 104 + 32 = 152
    FRM_TOTAL = 8 * 4 + w * h                               # 32 + w*h

    base_off   = HDR_SIZE + NUM_GROUPS * GRP_SIZE
    offsets_g0 = [base_off + i * FRM_TOTAL for i in range(8)]
    offsets_g1 = [base_off + (8 + i) * FRM_TOTAL for i in range(8)]

    # Paleta jako bajty
    pal_bytes = bytearray(256 * 3)
    for i, (r, g, b) in enumerate(palette_rgb[:256]):
        pal_bytes[i * 3]     = r
        pal_bytes[i * 3 + 1] = g
        pal_bytes[i * 3 + 2] = b

    out = bytearray()

    # --- Nagłówek główny ---
    out += u32(71)         # type = 71 (H3 interface sprite)
    out += u32(w)
    out += u32(h)
    out += u32(NUM_GROUPS) # 2 grupy
    out += pal_bytes       # 256 × 3 = 768 B

    # --- Nagłówek grupy 0 (normal) ---
    out += u32(0)
    out += u32(NUM_FRAMES)
    out += u32(0)
    out += u32(0)
    for i in range(NUM_FRAMES):
        out += fname(f"N{i:03d}.pcx")
    for off in offsets_g0:
        out += u32(off)

    # --- Nagłówek grupy 1 (hover) ---
    out += u32(1)
    out += u32(NUM_FRAMES)
    out += u32(0)
    out += u32(0)
    for i in range(NUM_FRAMES):
        out += fname(f"H{i:03d}.pcx")
    for off in offsets_g1:
        out += u32(off)

    # --- Dane klatek ---
    for px in frames_g0:
        out += frame_block(px)
    for px in frames_g1:
        out += frame_block(px)

    with open(path, 'wb') as f:
        f.write(out)

    expected = base_off + 16 * FRM_TOTAL
    print(f"Zapisano: {path}")
    print(f"  Rozmiar: {len(out)} bajtów (oczekiwano {expected})")
    print(f"  base_off={base_off}, FRM_TOTAL={FRM_TOTAL}, HDR={HDR_SIZE}, GRP_SIZE={GRP_SIZE}")


# ---------------------------------------------------------------------------
# Weryfikacja DEF (test odczytu)
# ---------------------------------------------------------------------------

def verify_def(path, w, h):
    with open(path, 'rb') as f:
        data = f.read()
    t   = struct.unpack_from('<I', data, 0)[0]
    fw  = struct.unpack_from('<I', data, 4)[0]
    fh  = struct.unpack_from('<I', data, 8)[0]
    ng  = struct.unpack_from('<I', data, 12)[0]
    print(f"Weryfikacja DEF: type={t}, size={fw}x{fh}, groups={ng}")
    assert t == 71, f"Zły typ: {t}"
    assert fw == w and fh == h, f"Zły rozmiar: {fw}x{fh}"
    assert ng == 2, f"Zła liczba grup: {ng}"
    pos = 784  # po nagłówku + palecie
    for g in range(2):
        gid = struct.unpack_from('<I', data, pos)[0]
        cnt = struct.unpack_from('<I', data, pos+4)[0]
        pos += 16
        names = [data[pos+i*13:pos+i*13+13].rstrip(b'\x00').decode('ascii', errors='ignore')
                 for i in range(cnt)]
        pos += 13 * cnt
        offsets = [struct.unpack_from('<I', data, pos+i*4)[0] for i in range(cnt)]
        pos += 4 * cnt
        print(f"  Grupa {gid}: {cnt} klatek, offsety={offsets[:2]}...")
        for oi, off in enumerate(offsets):
            ds = struct.unpack_from('<I', data, off)[0]
            fmt= struct.unpack_from('<I', data, off+4)[0]
            assert ds == w*h, f"g{g}f{oi}: zły dataSize {ds}"
            assert fmt == 0,  f"g{g}f{oi}: zły fmt {fmt}"
    print("  OK - DEF jest poprawny")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print("=== make_mybtn_def.py ===\n")
    print("Wczytywanie obrazów...")
    normal = Image.open(NORMAL_PNG).convert('RGBA')
    hover  = Image.open(HOVER_PNG).convert('RGBA')
    w, h = normal.size
    print(f"  Rozmiar: {w}x{h}")

    print("\nGenerowanie 16 wariantów kolorów gracza...")
    all_frames = []
    for state, src in [("normal", normal), ("hover", hover)]:
        for p in range(8):
            f = rotate_hue(src, PLAYER_HUES[p], SRC_HUE)
            all_frames.append(f)
            print(f"  {state} p{p} (hue {PLAYER_HUES[p]:3d}°): OK")

    print("\nKwantyzacja i indeksowanie...")
    palette_rgb, frames_indexed = build_indexed_frames(all_frames, w, h)

    frames_g0 = frames_indexed[:8]   # normal
    frames_g1 = frames_indexed[8:]   # hover

    print("\nZapis DEF...")
    write_def(OUT_DEF, frames_g0, frames_g1, palette_rgb, w, h)

    print("\nWeryfikacja...")
    verify_def(OUT_DEF, w, h)

    print("\n=== Gotowe! ===")
    print(f"Plik DEF: {OUT_DEF}")
    print("Skopiuj go do katalogu Data gry.")


if __name__ == '__main__':
    main()
