#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ekstraktor tekstów z plików LOD Heroes of Might and Magic III
Wyciąga teksty z kampanii i innych zasobów.

Użycie:
    python extract_lod_texts.py <plik.lod lub folder> [--output folder_wyjsciowy]
"""

import os
import sys
import struct
import json
import zlib
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, BinaryIO, Optional

class LODExtractor:
    """Ekstraktor plików LOD z Heroes 3"""

    def __init__(self):
        self.entries = []
        self.texts = []

    def extract_lod(self, filepath: str) -> Dict:
        """Ekstrahuje zawartość pliku LOD"""
        self.entries = []
        self.texts = []

        with open(filepath, 'rb') as f:
            # Nagłówek LOD
            magic = f.read(4)
            if magic != b'LOD\x00':
                print(f"  Nieprawidłowy nagłówek LOD: {magic}")
                return {'entries': [], 'texts': []}

            # Typ LOD (4 bajty)
            lod_type = f.read(4)

            # Liczba plików (4 bajty)
            file_count = struct.unpack('<I', f.read(4))[0]

            # Nieznane (80 bajtów)
            f.read(80)

            print(f"  Typ LOD: {lod_type}, Plików: {file_count}")

            # Odczytaj nagłówki plików
            for i in range(file_count):
                entry = self._read_entry_header(f)
                if entry:
                    self.entries.append(entry)

            # Wyciągnij teksty z interesujących plików
            for entry in self.entries:
                self._extract_text_from_entry(f, entry, filepath)

        return {
            'entries': self.entries,
            'texts': self.texts
        }

    def _read_entry_header(self, f: BinaryIO) -> Optional[Dict]:
        """Odczytuje nagłówek wpisu w LOD"""
        # Nazwa pliku (16 bajtów, null-terminated)
        name_bytes = f.read(16)
        name = name_bytes.split(b'\x00')[0].decode('latin-1')

        # Offset w pliku (4 bajty)
        offset = struct.unpack('<I', f.read(4))[0]

        # Rozmiar oryginalny (4 bajty)
        size_original = struct.unpack('<I', f.read(4))[0]

        # Typ pliku (4 bajty) - nieużywane w niektórych wersjach
        file_type = struct.unpack('<I', f.read(4))[0]

        # Rozmiar skompresowany (4 bajty)
        size_compressed = struct.unpack('<I', f.read(4))[0]

        return {
            'name': name,
            'offset': offset,
            'size_original': size_original,
            'size_compressed': size_compressed,
            'file_type': file_type
        }

    def _extract_text_from_entry(self, f: BinaryIO, entry: Dict, lod_path: str):
        """Wyciąga tekst z wpisu LOD"""
        name = entry['name'].lower()

        # Interesują nas pliki tekstowe
        text_extensions = ['.txt', '.str', '.h3c', '.json', '.xml', '.csv']
        is_text = any(name.endswith(ext) for ext in text_extensions)

        # Oraz pliki kampanii i eventów
        is_campaign = 'campaign' in name or name.endswith('.h3c')

        if not is_text and not is_campaign:
            return

        # Odczytaj dane pliku
        f.seek(entry['offset'])

        if entry['size_compressed'] > 0 and entry['size_compressed'] != entry['size_original']:
            # Dane skompresowane
            compressed_data = f.read(entry['size_compressed'])
            try:
                data = zlib.decompress(compressed_data)
            except:
                data = compressed_data
        else:
            data = f.read(entry['size_original'])

        # Próbuj zdekodować jako tekst
        text = self._try_decode_text(data)

        if text and len(text.strip()) > 10:
            self.texts.append({
                'lod_file': os.path.basename(lod_path),
                'entry_name': entry['name'],
                'size': len(data),
                'text': text
            })

    def _try_decode_text(self, data: bytes) -> Optional[str]:
        """Próbuje zdekodować dane jako tekst"""
        # Sprawdź czy to wygląda na tekst
        if not data:
            return None

        # Próbuj różne kodowania - CP1250 jako pierwsze dla polskich tekstów
        for encoding in ['cp1250', 'cp1252', 'utf-8', 'latin-1']:
            try:
                text = data.decode(encoding)
                # Sprawdź proporcję drukowalnych znaków
                printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t ')
                if len(text) > 0 and printable / len(text) > 0.85:
                    # Dodatkowe sprawdzenie - czy nie ma znaków kontrolnych
                    control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t ')
                    # Sprawdź znaki z zakresu 128-159 (znaki kontrolne w Windows-1250)
                    special_chars = sum(1 for c in text if 128 <= ord(c) < 160)
                    if control_chars == 0 and special_chars / len(text) < 0.05:
                        return text
            except:
                continue

        return None


class CampaignTextExtractor:
    """Specjalny ekstraktor dla tekstów kampanii"""

    def __init__(self):
        self.texts = []

    def extract_from_h3c(self, filepath: str) -> List[Dict]:
        """Ekstrahuje teksty z pliku kampanii .h3c"""
        self.texts = []
        filename = os.path.basename(filepath)

        try:
            # Pliki H3C mogą być skompresowane
            import gzip
            try:
                with gzip.open(filepath, 'rb') as f:
                    data = f.read()
            except:
                with open(filepath, 'rb') as f:
                    data = f.read()

            self._parse_campaign_data(data, filename)

        except Exception as e:
            print(f"  Błąd: {e}")

        return self.texts

    def _parse_campaign_data(self, data: bytes, filename: str):
        """Parsuje dane kampanii"""
        # Szukaj stringów w danych
        i = 0
        text_id = 0

        while i < len(data) - 4:
            # Sprawdź czy to może być długość stringa (format H3)
            length = struct.unpack('<I', data[i:i+4])[0]

            if 5 < length < 10000 and i + 4 + length <= len(data):
                text_data = data[i+4:i+4+length]

                # Sprawdź czy to tekst
                try:
                    text = text_data.decode('cp1250')
                    printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t ')
                    if printable / len(text) > 0.92:
                        # Dodatkowe sprawdzenie - czy nie ma znaków kontrolnych
                        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t ')
                        # Sprawdź znaki z zakresu 128-159 (znaki kontrolne w Windows-1250)
                        special_chars = sum(1 for c in text if 128 <= ord(c) < 160)
                        if control_chars == 0 and special_chars / len(text) < 0.05:
                            self.texts.append({
                                'file': filename,
                                'id': text_id,
                                'offset': i,
                                'text': text
                            })
                            text_id += 1
                            i += 4 + length
                            continue
                except:
                    pass

            i += 1


def extract_all_texts(input_path: str, output_dir: str):
    """Główna funkcja ekstrakcji"""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lod_extractor = LODExtractor()
    campaign_extractor = CampaignTextExtractor()

    all_texts = []

    # Zbierz pliki
    files_to_process = []
    if input_path.is_file():
        files_to_process.append(input_path)
    else:
        files_to_process.extend(input_path.rglob('*.lod'))
        files_to_process.extend(input_path.rglob('*.LOD'))
        files_to_process.extend(input_path.rglob('*.h3c'))

    print(f"Znaleziono {len(files_to_process)} plików...")

    for filepath in files_to_process:
        print(f"\nPrzetwarzanie: {filepath.name}")

        if filepath.suffix.lower() == '.lod':
            result = lod_extractor.extract_lod(str(filepath))
            texts = result['texts']

            # Zapisz listę wszystkich plików w LOD
            entries_file = output_dir / f"{filepath.stem}_entries.txt"
            with open(entries_file, 'w', encoding='utf-8') as f:
                f.write(f"Zawartość {filepath.name}:\n")
                f.write("=" * 60 + "\n")
                for entry in result['entries']:
                    f.write(f"{entry['name']:20} offset={entry['offset']:10} size={entry['size_original']:10}\n")

        elif filepath.suffix.lower() == '.h3c':
            texts = campaign_extractor.extract_from_h3c(str(filepath))
        else:
            continue

        if texts:
            all_texts.extend(texts)
            print(f"  Znaleziono {len(texts)} tekstów")

            # Zapisz teksty
            output_file = output_dir / f"{filepath.stem}_texts.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(texts, f, ensure_ascii=False, indent=2)

            txt_file = output_dir / f"{filepath.stem}_texts.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                for i, text_entry in enumerate(texts):
                    f.write(f"=== [{i}] {text_entry.get('entry_name', text_entry.get('id', ''))} ===\n")
                    f.write(f"{text_entry['text']}\n")
                    f.write("\n" + "-" * 40 + "\n\n")

    # Podsumowanie
    if all_texts:
        summary_file = output_dir / "_wszystkie_teksty.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(all_texts, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"Łącznie znaleziono {len(all_texts)} tekstów")
        print(f"Zapisano do: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Ekstraktor tekstów z plików LOD/H3C Heroes 3')
    parser.add_argument('input', help='Plik .lod/.h3c lub folder')
    parser.add_argument('--output', '-o', default='extracted_campaign_texts', help='Folder wyjściowy')

    args = parser.parse_args()
    extract_all_texts(args.input, args.output)


if __name__ == '__main__':
    main()
