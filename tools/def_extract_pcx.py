#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wyodrębnia klatki z pliku DEF Heroes 3 do osobnych plików PNG.
Każda klatka (stan przycisku) jest zapisywana jako osobny plik.
"""

import os
import struct
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Wymagana biblioteka PIL: pip install Pillow")
    exit(1)


def extract_def_frames(def_path, output_dir):
    """
    Wyodrębnia wszystkie klatki z pliku DEF do PNG.
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(def_path, 'rb') as f:
        file_data = f.read()

    pos = 0

    # Nagłówek DEF
    def_type = struct.unpack_from('<I', file_data, pos)[0]; pos += 4
    width = struct.unpack_from('<I', file_data, pos)[0]; pos += 4
    height = struct.unpack_from('<I', file_data, pos)[0]; pos += 4
    num_blocks = struct.unpack_from('<I', file_data, pos)[0]; pos += 4

    print(f"DEF: {Path(def_path).name}")
    print(f"  Typ: {def_type}")
    print(f"  Rozmiar: {width}x{height}")
    print(f"  Bloki: {num_blocks}")

    # Paleta (256 * 3 bajtów RGB)
    palette = []
    for i in range(256):
        r = file_data[pos]; pos += 1
        g = file_data[pos]; pos += 1
        b = file_data[pos]; pos += 1
        palette.append((r, g, b))

    # Specjalne kolory (0-7 to transparentne)
    transparent_indices = {0, 1, 2, 3, 4, 5, 6, 7}

    # Zapisz paletę do podglądu
    palette_img = Image.new('RGB', (256, 32), (0, 0, 0))
    for i, color in enumerate(palette):
        for y in range(32):
            palette_img.putpixel((i, y), color)
    palette_path = os.path.join(output_dir, "palette.png")
    palette_img.save(palette_path)
    print(f"  Paleta zapisana: palette.png")

    # Odczytaj bloki
    all_frames = []

    for b_idx in range(num_blocks):
        block_id = struct.unpack_from('<I', file_data, pos)[0]; pos += 4
        num_entries = struct.unpack_from('<I', file_data, pos)[0]; pos += 4
        pos += 8  # unknown

        print(f"  Blok {block_id}: {num_entries} klatek")

        # Nazwy klatek
        names = []
        for _ in range(num_entries):
            name = file_data[pos:pos+13].rstrip(b'\x00').decode('latin-1', errors='ignore')
            names.append(name)
            pos += 13

        # Offsety klatek
        offsets = []
        for _ in range(num_entries):
            offset = struct.unpack_from('<I', file_data, pos)[0]
            offsets.append(offset)
            pos += 4

        for frame_idx, (name, offset) in enumerate(zip(names, offsets)):
            all_frames.append({
                'block': block_id,
                'index': frame_idx,
                'name': name,
                'offset': offset
            })

    # Dekoduj i zapisz każdą klatkę
    frame_names = ["normal", "hover", "pressed", "disabled"]

    for frame_info in all_frames:
        try:
            img = decode_frame(file_data, frame_info['offset'], width, height, palette, transparent_indices)

            # Nazwa pliku
            state_name = frame_names[frame_info['index']] if frame_info['index'] < len(frame_names) else f"frame{frame_info['index']}"
            png_name = f"{state_name}.png"
            png_path = os.path.join(output_dir, png_name)

            img.save(png_path, 'PNG')
            print(f"    [{frame_info['index']}] {state_name}.png - {img.size[0]}x{img.size[1]}")

        except Exception as e:
            print(f"    Błąd dekodowania klatki {frame_info['index']}: {e}")

    print(f"\nWyodrębniono do: {output_dir}")
    return len(all_frames)


def decode_frame(data, offset, def_width, def_height, palette, transparent_indices):
    """Dekoduje pojedynczą klatkę."""
    pos = offset

    # Nagłówek klatki
    size = struct.unpack_from('<I', data, pos)[0]; pos += 4
    fmt = struct.unpack_from('<I', data, pos)[0]; pos += 4
    full_width = struct.unpack_from('<I', data, pos)[0]; pos += 4
    full_height = struct.unpack_from('<I', data, pos)[0]; pos += 4
    img_width = struct.unpack_from('<I', data, pos)[0]; pos += 4
    img_height = struct.unpack_from('<I', data, pos)[0]; pos += 4
    left_margin = struct.unpack_from('<i', data, pos)[0]; pos += 4
    top_margin = struct.unpack_from('<i', data, pos)[0]; pos += 4

    # Utwórz obraz RGBA
    img = Image.new('RGBA', (full_width, full_height), (0, 0, 0, 0))
    pixels = img.load()

    data_start = pos

    if fmt == 0:
        # Format 0: surowe piksele
        for y in range(img_height):
            for x in range(img_width):
                idx = data[pos]; pos += 1
                px = left_margin + x
                py = top_margin + y
                if 0 <= px < full_width and 0 <= py < full_height:
                    if idx in transparent_indices:
                        pixels[px, py] = (0, 0, 0, 0)
                    else:
                        pixels[px, py] = (*palette[idx], 255)

    elif fmt == 1:
        # Format 1: offsety linii + RLE
        line_offsets = []
        for y in range(img_height):
            line_offsets.append(struct.unpack_from('<I', data, pos)[0])
            pos += 4

        for y, line_off in enumerate(line_offsets):
            line_pos = data_start + line_off
            x = 0
            while x < img_width:
                if line_pos >= len(data):
                    break
                cmd = data[line_pos]; line_pos += 1

                if cmd == 0xFF:
                    break
                elif cmd & 0x80:
                    skip = (cmd & 0x7F) + 1
                    x += skip
                else:
                    count = (cmd & 0x7F) + 1
                    for _ in range(count):
                        if x >= img_width or line_pos >= len(data):
                            break
                        idx = data[line_pos]; line_pos += 1
                        px = left_margin + x
                        py = top_margin + y
                        if 0 <= px < full_width and 0 <= py < full_height:
                            if idx in transparent_indices:
                                pixels[px, py] = (0, 0, 0, 0)
                            else:
                                pixels[px, py] = (*palette[idx], 255)
                        x += 1

    elif fmt == 2:
        # Format 2
        line_offsets = []
        for y in range(img_height):
            line_offsets.append(struct.unpack_from('<H', data, pos)[0])
            pos += 2

        for y, line_off in enumerate(line_offsets):
            line_pos = data_start + line_off
            x = 0
            while x < img_width:
                if line_pos + 1 >= len(data):
                    break
                segment = data[line_pos]; line_pos += 1
                length = data[line_pos] + 1; line_pos += 1

                if segment == 0xFF:
                    x += length
                else:
                    color = palette[segment]
                    for _ in range(length):
                        if x >= img_width:
                            break
                        px = left_margin + x
                        py = top_margin + y
                        if 0 <= px < full_width and 0 <= py < full_height:
                            if segment in transparent_indices:
                                pixels[px, py] = (0, 0, 0, 0)
                            else:
                                pixels[px, py] = (*color, 255)
                        x += 1

    elif fmt == 3:
        # Format 3
        line_offsets = []
        for y in range(img_height):
            line_offsets.append(struct.unpack_from('<H', data, pos)[0])
            pos += 2

        for y, line_off in enumerate(line_offsets):
            line_pos = data_start + line_off
            x = 0

            while x < img_width:
                if line_pos >= len(data):
                    break

                cmd = data[line_pos]; line_pos += 1
                length = (cmd >> 5) + 1
                code = cmd & 0x1F

                if code == 0x1F:
                    for _ in range(length):
                        if x >= img_width or line_pos >= len(data):
                            break
                        idx = data[line_pos]; line_pos += 1
                        px = left_margin + x
                        py = top_margin + y
                        if 0 <= px < full_width and 0 <= py < full_height:
                            if idx in transparent_indices:
                                pixels[px, py] = (0, 0, 0, 0)
                            else:
                                pixels[px, py] = (*palette[idx], 255)
                        x += 1
                else:
                    for _ in range(length):
                        if x >= img_width:
                            break
                        px = left_margin + x
                        py = top_margin + y
                        if 0 <= px < full_width and 0 <= py < full_height:
                            if code in transparent_indices:
                                pixels[px, py] = (0, 0, 0, 0)
                            else:
                                pixels[px, py] = (*palette[code], 255)
                        x += 1

    return img


if __name__ == '__main__':
    import sys

    # Domyślnie iOKAY.def
    def_path = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\extracted_buttons\iOKAY.def"
    output_dir = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\iOKAY_frames"

    if len(sys.argv) > 1:
        def_path = sys.argv[1]
        output_dir = Path(def_path).stem + "_frames"

    extract_def_frames(def_path, output_dir)
