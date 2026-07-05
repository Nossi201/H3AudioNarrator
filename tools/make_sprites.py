#!/usr/bin/env python3
"""
make_sprites.py - generuje pliki DEF (H3 Type-71) dla PlayerDlg.

Plik wyjsciowy             Rozmiar   Uzycie w PlayerDlg
  AUDIBTN.DEF              64 x 30   Play / Stop / Reset / Zamknij
  AUDIARR.DEF              22 x 22   [<]  [>]  (nawigacja)
  AUDIDEL.DEF              66 x 22   [Usun]

Kazdy DEF ma 1 grupe (group 0) z 4 klatkami (jak iOKAY.def):
  klatka 0 - normal    (n)
  klatka 1 - pressed   (s/p)
  klatka 2 - disabled  (d)
  klatka 3 - hover     (h)

FORMAT: Type 71 (0x47) - H3 interface sprites - identyczny z iOKAY.def
        compression = 0 (raw pixel data, pelne piksele)

Kopiuj wygenerowane pliki do:
  <HoMM3>\\Data\\
"""

import struct
import os
import sys


# ---------------------------------------------------------------------------
# Paleta (256 kolorow RGB)  -  kamienna faktura H3
# ---------------------------------------------------------------------------

def make_palette() -> bytes:
    pal = bytearray(256 * 3)

    def sc(i: int, r: int, g: int, b: int):
        pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2] = r, g, b

    # Indeks 0 = transparent (H3 pomija piksele o indeksie 0)
    sc(0,   0,   0,   0)
    # Indeksy robocze 1-15
    sc(1,  24,  20,  16)   # ciemna ramka zewnetrzna
    sc(2,  56,  48,  40)   # ramka wewnetrzna / cien
    sc(3,  80,  70,  58)   # cien krawedzi (wcisniety-gora)
    sc(4, 104,  92,  78)   # wypelnienie ciemne
    sc(5, 120, 108,  92)   # wypelnienie srednie
    sc(6, 138, 124, 106)   # wypelnienie jasne (gora przycisku)
    sc(7, 160, 144, 124)   # jasny highlight (krawedz gora-lewo)
    sc(8, 178, 162, 140)   # jasny highlight (2. warstwa)
    sc(9,  72,  64,  54)   # wypelnienie wcisnietego
    sc(10, 56,  50,  42)   # wypelnienie disabled (przyciemnione)

    # Uzupelnienie palety gradientem (16-255)
    for i in range(16, 256):
        t = (i - 16) / 239.0
        r = int(40 + t * 140)
        g = int(36 + t * 124)
        b = int(30 + t * 106)
        sc(i, min(r, 255), min(g, 255), min(b, 255))

    return bytes(pal)


# ---------------------------------------------------------------------------
# Generatory pikseli
# ---------------------------------------------------------------------------

def make_frame_normal(w: int, h: int) -> bytes:
    """Stan normalny: jasna krawedz gora-lewo, cien dol-prawo."""
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                c = 1
            elif x == 1 or y == 1:
                c = 8
            elif x == 2 or y == 2:
                c = 7
            elif x == w - 2 or y == h - 2:
                c = 2
            elif x == w - 3 or y == h - 3:
                c = 3
            else:
                frac = y / (h - 1)
                c = 7 if frac < 0.25 else 6 if frac < 0.55 else 5
            px[y * w + x] = c
    return bytes(px)


def make_frame_pressed(w: int, h: int) -> bytes:
    """Stan wcisniety: odwrocony relief."""
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                c = 1
            elif x == 1 or y == 1:
                c = 2
            elif x == 2 or y == 2:
                c = 3
            elif x == w - 2 or y == h - 2:
                c = 7
            elif x == w - 3 or y == h - 3:
                c = 6
            else:
                c = 9
            px[y * w + x] = c
    return bytes(px)


def make_frame_disabled(w: int, h: int) -> bytes:
    """Stan disabled: przyciemniony normal."""
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                c = 1
            elif x == 1 or y == 1:
                c = 2
            elif x == 2 or y == 2:
                c = 2
            elif x == w - 2 or y == h - 2:
                c = 1
            elif x == w - 3 or y == h - 3:
                c = 1
            else:
                c = 10  # przyciemnione wypelnienie
            px[y * w + x] = c
    return bytes(px)


def make_frame_hover(w: int, h: int) -> bytes:
    """Stan hover: nieco jasniejszy normal."""
    px = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                c = 1
            elif x == 1 or y == 1:
                c = 8
            elif x == 2 or y == 2:
                c = 8
            elif x == w - 2 or y == h - 2:
                c = 3
            elif x == w - 3 or y == h - 3:
                c = 4
            else:
                frac = y / (h - 1)
                c = 8 if frac < 0.25 else 7 if frac < 0.55 else 6
            px[y * w + x] = c
    return bytes(px)


# ---------------------------------------------------------------------------
# Zapis H3 DEF  (Type 71 = 0x47, 1 grupa, 4 klatki)
# Format identyczny jak iOKAY.def z H3sprite.lod
# ---------------------------------------------------------------------------

def write_def(w: int, h: int, path: str):
    palette      = make_palette()           # 768 B
    pix_normal   = make_frame_normal(w, h)  # klatka 0: n
    pix_pressed  = make_frame_pressed(w, h) # klatka 1: s (selected/pressed)
    pix_disabled = make_frame_disabled(w, h)# klatka 2: d
    pix_hover    = make_frame_hover(w, h)   # klatka 3: h

    NUM_FRAMES = 4

    # ---- rozmiary bloków ----
    HDR_SIZE  = 4 * 4 + 768                        # type+w+h+grpCount + paleta = 784
    GRP_HDR   = 4 * 4                              # groupID+frameCount+unk+unk = 16
    GRP_NAMES = 13 * NUM_FRAMES                    # nazwy klatek = 52
    GRP_OFFS  = 4  * NUM_FRAMES                    # offsety klatek = 16
    GRP_SIZE  = GRP_HDR + GRP_NAMES + GRP_OFFS     # = 84
    FRM_HDR   = 8 * 4                              # 8 pol uint32 = 32
    FRM_DATA  = w * h                              # piksele (raw, brak kompresji)
    FRM_TOTAL = FRM_HDR + FRM_DATA

    base_off  = HDR_SIZE + GRP_SIZE                # offset pierwszej klatki
    offset0   = base_off + 0 * FRM_TOTAL           # normal
    offset1   = base_off + 1 * FRM_TOTAL           # pressed
    offset2   = base_off + 2 * FRM_TOTAL           # disabled
    offset3   = base_off + 3 * FRM_TOTAL           # hover

    def u32(v: int) -> bytes:
        return struct.pack('<I', v)

    def fname(s: str) -> bytes:
        return s.encode('ascii').ljust(13, b'\x00')[:13]

    def frame_block(pixels: bytes) -> bytearray:
        blk = bytearray()
        blk += u32(FRM_DATA)  # dataSize (raw: dokladnie w*h bajtow)
        blk += u32(0)         # compression = 0 (raw)
        blk += u32(w)         # fullWidth
        blk += u32(h)         # fullHeight
        blk += u32(w)         # frameWidth
        blk += u32(h)         # frameHeight
        blk += u32(0)         # xOffset
        blk += u32(0)         # yOffset
        blk += pixels
        return blk

    out = bytearray()

    # ---------- Glowny naglowek ----------
    out += u32(71)        # type = 71 (0x47) - H3 interface/button sprite
    out += u32(w)
    out += u32(h)
    out += u32(1)         # 1 grupa
    out += palette

    # ---------- Naglowek grupy 0 ----------
    out += u32(0)                # groupID = 0
    out += u32(NUM_FRAMES)       # frameCount = 4
    out += u32(0)                # unk1
    out += u32(0)                # unk2

    # Nazwy klatek (n, s, d, h - jak w iOKAY.def)
    out += fname("N000.pcx")     # 0: normal
    out += fname("S000.pcx")     # 1: selected / pressed
    out += fname("D000.pcx")     # 2: disabled
    out += fname("H000.pcx")     # 3: hover

    # Offsety klatek (od poczatku pliku)
    out += u32(offset0)
    out += u32(offset1)
    out += u32(offset2)
    out += u32(offset3)

    # ---------- Klatki ----------
    out += frame_block(pix_normal)
    out += frame_block(pix_pressed)
    out += frame_block(pix_disabled)
    out += frame_block(pix_hover)

    with open(path, 'wb') as f:
        f.write(out)

    print(f"  {os.path.basename(path):20s}  {w:3d}x{h:2d}  {len(out):5d} B  type=71  frames=4")


# ---------------------------------------------------------------------------
# Wejscie glowne
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    out_dir = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(out_dir, exist_ok=True)

    print("Generowanie spriteow H3 Type-71 dla PlayerDlg:\n")
    write_def(64, 30, os.path.join(out_dir, 'AUDIBTN.DEF'))
    write_def(22, 22, os.path.join(out_dir, 'AUDIARR.DEF'))
    write_def(66, 22, os.path.join(out_dir, 'AUDIDEL.DEF'))

    print("\nGotowe!")
