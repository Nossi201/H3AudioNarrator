#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Konwertuje pliki DEF (Heroes 3) na PNG.
Bazowane na Heroes3ResourceManager (https://github.com/brandshub/Heroes3ResourceManager)
"""

import os
import struct
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Wymagana biblioteka PIL: pip install Pillow")
    exit(1)


def extract_def_to_png(def_path, output_dir):
    """
    Wyodrębnia wszystkie klatki z pliku DEF do PNG.
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(def_path, 'rb') as f:
        data = f.read()

    # Nagłówek DEF (offset 0x00 - 0x0F)
    def_id = struct.unpack_from('<I', data, 0x00)[0]
    width = struct.unpack_from('<I', data, 0x04)[0]
    height = struct.unpack_from('<I', data, 0x08)[0]
    block_count = struct.unpack_from('<I', data, 0x0C)[0]

    print(f"DEF: {Path(def_path).name}")
    print(f"  ID: {def_id}, Rozmiar: {width}x{height}, Bloki: {block_count}")

    # Paleta kolorów (offset 0x10, 256 * 3 bajtów RGB)
    palette = []
    for i in range(256):
        r = data[0x10 + i * 3]
        g = data[0x10 + i * 3 + 1]
        b = data[0x10 + i * 3 + 2]
        palette.append((r, g, b))

    # Zapisz paletę
    palette_img = Image.new('RGB', (256, 32))
    for i, color in enumerate(palette):
        for y in range(32):
            palette_img.putpixel((i, y), color)
    palette_img.save(os.path.join(output_dir, "palette.png"))
    print(f"  Paleta zapisana")

    # Nagłówki bloków zaczynają się na offset 0x310
    pos = 0x310

    frame_idx = 0
    frame_names = ["normal", "hover", "pressed", "disabled"]

    for block_num in range(block_count):
        # Nagłówek bloku
        block_id = struct.unpack_from('<I', data, pos)[0]; pos += 4
        entries_count = struct.unpack_from('<I', data, pos)[0]; pos += 4
        pos += 8  # unknown bytes

        print(f"  Blok {block_id}: {entries_count} klatek")

        # Nazwy klatek (13 bajtów każda)
        names = []
        for _ in range(entries_count):
            name = data[pos:pos+13].rstrip(b'\x00').decode('latin-1', errors='ignore')
            names.append(name)
            pos += 13

        # Offsety klatek (4 bajty każdy)
        offsets = []
        for _ in range(entries_count):
            offset = struct.unpack_from('<I', data, pos)[0]
            offsets.append(offset)
            pos += 4

        # Dekoduj każdą klatkę
        for i, (name, offset) in enumerate(zip(names, offsets)):
            try:
                img = decode_sprite(data, offset, width, height, palette)

                # Nazwa pliku
                state_name = frame_names[frame_idx] if frame_idx < len(frame_names) else f"frame{frame_idx}"
                png_path = os.path.join(output_dir, f"{state_name}.png")
                img.save(png_path, 'PNG')
                print(f"    [{frame_idx}] {state_name}.png ({img.size[0]}x{img.size[1]})")

                frame_idx += 1

            except Exception as e:
                print(f"    Błąd klatki {i}: {e}")
                import traceback
                traceback.print_exc()

    print(f"\nZapisano do: {output_dir}")


def decode_sprite(data, offset, def_width, def_height, palette):
    """
    Dekoduje sprite z danych DEF.
    """
    # Nagłówek sprite'a (32 bajty)
    size = struct.unpack_from('<I', data, offset)[0]
    fmt = struct.unpack_from('<I', data, offset + 4)[0]
    full_width = struct.unpack_from('<I', data, offset + 8)[0]
    full_height = struct.unpack_from('<I', data, offset + 12)[0]
    img_width = struct.unpack_from('<I', data, offset + 16)[0]
    img_height = struct.unpack_from('<I', data, offset + 20)[0]
    left_margin = struct.unpack_from('<i', data, offset + 24)[0]
    top_margin = struct.unpack_from('<i', data, offset + 28)[0]

    # Utwórz obraz RGBA z transparentnym tłem
    img = Image.new('RGBA', (full_width, full_height), (0, 0, 0, 0))

    # Dane sprite'a zaczynają się po nagłówku
    data_offset = offset + 32

    if fmt == 0:
        # Format 0: surowe piksele (bez kompresji)
        decode_format_0(data, data_offset, img, img_width, img_height, left_margin, top_margin, palette)

    elif fmt == 1:
        # Format 1: RLE z offsetami linii (4 bajty na linię)
        decode_format_1(data, data_offset, img, img_width, img_height, left_margin, top_margin, palette)

    elif fmt == 2:
        # Format 2: RLE z offsetami linii (2 bajty na linię)
        decode_format_2(data, data_offset, img, img_width, img_height, left_margin, top_margin, palette)

    elif fmt == 3:
        # Format 3: podobny do 2, ale z innym kodowaniem
        decode_format_3(data, data_offset, img, img_width, img_height, left_margin, top_margin, palette)

    return img


def is_special_color(idx):
    """Sprawdza czy indeks to specjalny kolor (transparentny/cień)."""
    return idx < 8


def decode_format_0(data, offset, img, width, height, left, top, palette):
    """Format 0: surowe piksele."""
    pos = offset
    for y in range(height):
        for x in range(width):
            idx = data[pos]; pos += 1
            px, py = left + x, top + y
            if 0 <= px < img.width and 0 <= py < img.height:
                if is_special_color(idx):
                    img.putpixel((px, py), (0, 0, 0, 0))
                else:
                    img.putpixel((px, py), (*palette[idx], 255))


def decode_format_1(data, offset, img, width, height, left, top, palette):
    """Format 1: RLE z 4-bajtowymi offsetami linii."""
    # Najpierw odczytaj offsety linii
    line_offsets = []
    for y in range(height):
        line_offsets.append(struct.unpack_from('<I', data, offset + y * 4)[0])

    for y, line_off in enumerate(line_offsets):
        pos = offset + line_off
        x = 0

        while x < width:
            if pos >= len(data):
                break

            code = data[pos]; pos += 1
            length = data[pos] + 1; pos += 1

            if code == 0xFF:
                # Różne kolory - odczytaj length pikseli
                for _ in range(length):
                    if x >= width or pos >= len(data):
                        break
                    idx = data[pos]; pos += 1
                    px, py = left + x, top + y
                    if 0 <= px < img.width and 0 <= py < img.height:
                        if is_special_color(idx):
                            img.putpixel((px, py), (0, 0, 0, 0))
                        else:
                            img.putpixel((px, py), (*palette[idx], 255))
                    x += 1
            else:
                # Powtórzenie koloru code, length razy
                for _ in range(length):
                    if x >= width:
                        break
                    px, py = left + x, top + y
                    if 0 <= px < img.width and 0 <= py < img.height:
                        if is_special_color(code):
                            img.putpixel((px, py), (0, 0, 0, 0))
                        else:
                            img.putpixel((px, py), (*palette[code], 255))
                    x += 1


def decode_format_2(data, offset, img, width, height, left, top, palette):
    """Format 2: RLE z 2-bajtowymi offsetami linii."""
    # Odczytaj offsety linii (2 bajty każdy)
    line_offsets = []
    for y in range(height):
        line_offsets.append(struct.unpack_from('<H', data, offset + y * 2)[0])

    for y, line_off in enumerate(line_offsets):
        pos = offset + line_off
        x = 0

        while x < width:
            if pos >= len(data):
                break

            segment = data[pos]; pos += 1

            # Dolne 5 bitów = długość - 1
            length = (segment & 0x1F) + 1
            # Górne 3 bity = typ
            code_type = (segment >> 5) & 0x07

            if code_type == 7:
                # Typ 7: różne kolory, odczytaj length pikseli
                for _ in range(length):
                    if x >= width or pos >= len(data):
                        break
                    idx = data[pos]; pos += 1
                    px, py = left + x, top + y
                    if 0 <= px < img.width and 0 <= py < img.height:
                        if is_special_color(idx):
                            img.putpixel((px, py), (0, 0, 0, 0))
                        else:
                            img.putpixel((px, py), (*palette[idx], 255))
                    x += 1
            else:
                # Typ 0-6: powtórzenie koloru z palety specjalnej (indeks = code_type)
                for _ in range(length):
                    if x >= width:
                        break
                    px, py = left + x, top + y
                    if 0 <= px < img.width and 0 <= py < img.height:
                        # Specjalne kolory 0-6 to transparentność/cienie
                        img.putpixel((px, py), (0, 0, 0, 0))
                    x += 1


def decode_format_3(data, offset, img, width, height, left, top, palette):
    """Format 3: podobny do formatu 2."""
    # Offsety linii (2 bajty)
    line_offsets = []
    for y in range(height):
        line_offsets.append(struct.unpack_from('<H', data, offset + y * 2)[0])

    for y, line_off in enumerate(line_offsets):
        pos = offset + line_off
        x = 0

        while x < width:
            if pos >= len(data):
                break

            segment = data[pos]; pos += 1

            # Format 3: dolne 5 bitów = długość - 1, górne 3 bity = typ
            length = (segment & 0x1F) + 1
            code_type = (segment >> 5) & 0x07

            if code_type == 7:
                # Różne kolory
                for _ in range(length):
                    if x >= width or pos >= len(data):
                        break
                    idx = data[pos]; pos += 1
                    px, py = left + x, top + y
                    if 0 <= px < img.width and 0 <= py < img.height:
                        if is_special_color(idx):
                            img.putpixel((px, py), (0, 0, 0, 0))
                        else:
                            img.putpixel((px, py), (*palette[idx], 255))
                    x += 1
            else:
                # Specjalny kolor (transparentny)
                for _ in range(length):
                    if x >= width:
                        break
                    px, py = left + x, top + y
                    if 0 <= px < img.width and 0 <= py < img.height:
                        img.putpixel((px, py), (0, 0, 0, 0))
                    x += 1


if __name__ == '__main__':
    import sys

    def_path = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\extracted_buttons\iOKAY.def"
    output_dir = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\iOKAY_frames"

    if len(sys.argv) > 1:
        def_path = sys.argv[1]
        output_dir = Path(def_path).stem + "_frames"

    extract_def_to_png(def_path, output_dir)
