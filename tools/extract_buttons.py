#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wyodrębnia przyciski (pliki DEF) z archiwów LOD Heroes 3.
Przyciski interfejsu zaczynają się od 'i' (np. iCancel.def, iOkay.def).
"""

import os
import struct
import zlib
from pathlib import Path

# Ścieżka do głównego archiwum sprite
LOD_PATH = r"F:\gry\h3-Chro-Hdmod(modowanie)\HoMM 3 Complete\Data\H3sprite.lod"
OUTPUT_DIR = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\extracted_buttons"


def read_lod_index(filepath):
    """Odczytuje indeks plików z archiwum LOD."""
    files = []

    with open(filepath, 'rb') as f:
        # Nagłówek LOD
        magic = f.read(4)
        if magic != b'LOD\x00':
            print(f"Nieprawidłowy format LOD: {magic}")
            return files

        f.seek(8)
        file_count = struct.unpack('<I', f.read(4))[0]
        print(f"Liczba plików w archiwum: {file_count}")

        # Indeks zaczyna się od offsetu 92
        f.seek(92)

        for i in range(file_count):
            # Każdy wpis ma 32 bajty
            entry = f.read(32)
            if len(entry) < 32:
                break

            # Nazwa pliku (16 bajtów, null-terminated)
            name = entry[:16].rstrip(b'\x00').decode('latin-1')

            # Offset, rozmiar oryginalny, typ, rozmiar skompresowany
            offset = struct.unpack('<I', entry[16:20])[0]
            size_orig = struct.unpack('<I', entry[20:24])[0]
            file_type = struct.unpack('<I', entry[24:28])[0]
            size_comp = struct.unpack('<I', entry[28:32])[0]

            files.append({
                'name': name,
                'offset': offset,
                'size_orig': size_orig,
                'size_comp': size_comp,
                'type': file_type
            })

    return files


def extract_file(lod_path, file_info, output_dir):
    """Wyodrębnia pojedynczy plik z archiwum LOD."""
    with open(lod_path, 'rb') as f:
        f.seek(file_info['offset'])

        if file_info['size_comp'] > 0:
            # Plik jest skompresowany
            compressed = f.read(file_info['size_comp'])
            try:
                data = zlib.decompress(compressed)
            except zlib.error:
                # Może nie być skompresowany mimo size_comp
                data = compressed
        else:
            # Plik nie jest skompresowany
            data = f.read(file_info['size_orig'])

        # Zapisz plik
        output_path = os.path.join(output_dir, file_info['name'])
        with open(output_path, 'wb') as out:
            out.write(data)

        return output_path


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Odczytywanie archiwum: {LOD_PATH}")
    files = read_lod_index(LOD_PATH)

    # Znajdź wszystkie pliki DEF zaczynające się od 'i' (interface buttons)
    button_files = [f for f in files if f['name'].lower().startswith('i') and f['name'].lower().endswith('.def')]

    print(f"\nZnaleziono {len(button_files)} przycisków interfejsu:")

    # Sortuj alfabetycznie
    button_files.sort(key=lambda x: x['name'].lower())

    # Wyświetl listę i wyodrębnij
    for bf in button_files:
        print(f"  {bf['name']:20} ({bf['size_orig']:6} bajtów)")
        try:
            extract_file(LOD_PATH, bf, OUTPUT_DIR)
        except Exception as e:
            print(f"    BŁĄD: {e}")

    print(f"\nWyodrębniono do: {OUTPUT_DIR}")

    # Dodatkowo wyodrębnij kilka użytecznych przycisków z innych nazw
    useful_buttons = ['cancel', 'okay', 'ok', 'no', 'yes', 'exit', 'info']
    other_buttons = [f for f in files
                     if f['name'].lower().endswith('.def')
                     and any(btn in f['name'].lower() for btn in useful_buttons)
                     and not f['name'].lower().startswith('i')]

    if other_buttons:
        print(f"\nDodatkowe przyciski ({len(other_buttons)}):")
        for bf in other_buttons:
            print(f"  {bf['name']:20} ({bf['size_orig']:6} bajtów)")
            try:
                extract_file(LOD_PATH, bf, OUTPUT_DIR)
            except Exception as e:
                print(f"    BŁĄD: {e}")


if __name__ == '__main__':
    main()
