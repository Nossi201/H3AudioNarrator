#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ekstraktor tekstów kampanii z plików LOD Heroes of Might and Magic III
Specjalizuje się w wyciąganiu tekstów fabularnych z plików .h3c wewnątrz LOD.

Użycie:
    python extract_campaign_texts.py <plik.lod lub folder> [--output folder_wyjsciowy]
"""

import os
import sys
import struct
import json
import zlib
import gzip
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, BinaryIO, Optional
from io import BytesIO


class H3CampaignExtractor:
    """Ekstraktor tekstów z plików kampanii H3C"""

    def __init__(self):
        self.texts = []

    def extract_strings_from_binary(self, data: bytes, source_name: str) -> List[Dict]:
        """
        Wyciąga stringi z binarnych danych kampanii.
        Heroes 3 używa length-prefixed strings (4 bajty długość + tekst).
        """
        texts = []
        i = 0
        text_id = 0

        while i < len(data) - 4:
            # Odczytaj potencjalną długość stringa
            try:
                length = struct.unpack('<I', data[i:i+4])[0]
            except:
                i += 1
                continue

            # Sprawdź czy to sensowna długość (stringi kampanii zwykle mają 5-5000 znaków)
            if 5 <= length <= 10000 and i + 4 + length <= len(data):
                text_data = data[i+4:i+4+length]

                # Sprawdź czy to wygląda na tekst
                text = self._try_decode_string(text_data)
                if text:
                    # Filtruj - chcemy tylko sensowne teksty fabularne
                    if self._is_narrative_text(text):
                        texts.append({
                            'source': source_name,
                            'id': text_id,
                            'offset': i,
                            'length': length,
                            'text': text
                        })
                        text_id += 1
                    i += 4 + length
                    continue

            i += 1

        return texts

    def _try_decode_string(self, data: bytes) -> Optional[str]:
        """Próbuje zdekodować bajty jako tekst"""
        for encoding in ['cp1250', 'cp1252', 'utf-8', 'latin-1']:
            try:
                text = data.decode(encoding)
                # Sprawdź proporcję drukowalnych znaków
                if len(text) == 0:
                    continue
                printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t ')
                ratio = printable / len(text)
                if ratio > 0.92:
                    # Dodatkowe sprawdzenie - czy nie ma znaków kontrolnych
                    control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t ')
                    # Sprawdź znaki z zakresu 128-159 (znaki kontrolne w Windows-1250)
                    special_chars = sum(1 for c in text if 128 <= ord(c) < 160)
                    if control_chars == 0 and special_chars / len(text) < 0.05:
                        return text.strip()
            except:
                continue
        return None

    def _is_narrative_text(self, text: str) -> bool:
        """Sprawdza czy tekst wygląda na tekst fabularny"""
        # Odrzuć bardzo krótkie teksty
        if len(text) < 10:
            return False

        # Odrzuć teksty które wyglądają na nazwy plików
        if text.lower().endswith(('.pcx', '.def', '.wav', '.mp3', '.h3m', '.h3c', '.txt', '.bmp', '.msk')):
            return False

        # Odrzuć teksty które wyglądają na ścieżki
        if '\\' in text or text.startswith('/'):
            return False

        # Odrzuć teksty które wyglądają na kod lub dane binarne
        if text.count('{') > 3 or text.count('}') > 3:
            return False

        # Odrzuć teksty z dużą ilością znaków specjalnych (typowe dla danych binarnych)
        weird_chars = sum(1 for c in text if ord(c) > 255 or (128 <= ord(c) < 160))
        if len(text) > 0 and weird_chars / len(text) > 0.1:
            return False

        # Odrzuć teksty zawierające sekwencje bajtów zerowych jako string
        if '\x00' in text:
            return False

        # Akceptuj teksty które wyglądają na narrację
        # (zawierają spacje, kropki, przecinki - typowe dla zdań)
        has_spaces = ' ' in text
        has_punctuation = any(c in text for c in '.!?,;:')

        return has_spaces or has_punctuation or len(text) > 30


class LODCampaignExtractor:
    """Ekstraktor kampanii z plików LOD"""

    def __init__(self):
        self.entries = []
        self.campaign_texts = []
        self.h3c_extractor = H3CampaignExtractor()

    def extract_from_lod(self, filepath: str) -> Dict:
        """Ekstrahuje kampanie z pliku LOD"""
        self.entries = []
        self.campaign_texts = []

        with open(filepath, 'rb') as f:
            # Nagłówek LOD
            magic = f.read(4)
            if magic != b'LOD\x00':
                print(f"  Nieprawidłowy nagłówek LOD: {magic}")
                return {'entries': [], 'campaign_texts': []}

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

            # Znajdź i przetwórz pliki kampanii
            for entry in self.entries:
                name = entry['name'].lower()

                # Interesują nas pliki .h3c (kampanie)
                if name.endswith('.h3c'):
                    print(f"    Przetwarzanie kampanii: {entry['name']}")
                    texts = self._extract_campaign_texts(f, entry, filepath)
                    if texts:
                        self.campaign_texts.extend(texts)
                        print(f"      Znaleziono {len(texts)} tekstów")

        return {
            'entries': self.entries,
            'campaign_texts': self.campaign_texts
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

        # Typ pliku (4 bajty)
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

    def _extract_campaign_texts(self, f: BinaryIO, entry: Dict, lod_path: str) -> List[Dict]:
        """Wyciąga teksty z pliku kampanii"""
        f.seek(entry['offset'])

        # Pobierz dane - mogą być skompresowane
        if entry['size_compressed'] > 0 and entry['size_compressed'] != entry['size_original']:
            compressed_data = f.read(entry['size_compressed'])
            try:
                data = zlib.decompress(compressed_data)
                print(f"      Dekompresja zlib: {entry['size_compressed']} -> {len(data)} bajtów")
            except zlib.error as e:
                print(f"      Błąd dekompresji zlib: {e}")
                # Spróbuj jako gzip
                try:
                    f.seek(entry['offset'])
                    compressed_data = f.read(entry['size_compressed'])
                    data = gzip.decompress(compressed_data)
                    print(f"      Dekompresja gzip: {entry['size_compressed']} -> {len(data)} bajtów")
                except:
                    # Użyj surowych danych
                    data = compressed_data
                    print(f"      Używam surowych danych ({len(data)} bajtów)")
        else:
            data = f.read(entry['size_original'])
            print(f"      Nieskompresowane dane: {len(data)} bajtów")

        # Plik H3C sam w sobie może być skompresowany gzip
        # Sprawdź nagłówek gzip (1f 8b)
        if len(data) >= 2 and data[0:2] == b'\x1f\x8b':
            try:
                data = gzip.decompress(data)
                print(f"      Dodatkowa dekompresja gzip wewnętrzna: {len(data)} bajtów")
            except:
                pass

        # Wyciągnij stringi z danych kampanii
        source_name = f"{os.path.basename(lod_path)}:{entry['name']}"
        return self.h3c_extractor.extract_strings_from_binary(data, source_name)


def extract_campaign_texts(input_path: str, output_dir: str):
    """Główna funkcja ekstrakcji"""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extractor = LODCampaignExtractor()
    all_campaign_texts = []

    # Zbierz pliki LOD
    files_to_process = []
    if input_path.is_file():
        files_to_process.append(input_path)
    else:
        files_to_process.extend(input_path.rglob('*.lod'))
        files_to_process.extend(input_path.rglob('*.LOD'))

    print(f"Znaleziono {len(files_to_process)} plików LOD...")

    for filepath in files_to_process:
        print(f"\nPrzetwarzanie: {filepath.name}")

        result = extractor.extract_from_lod(str(filepath))

        # Zapisz listę plików w LOD
        entries_file = output_dir / f"{filepath.stem}_contents.txt"
        with open(entries_file, 'w', encoding='utf-8') as f:
            f.write(f"Zawartość {filepath.name}:\n")
            f.write("=" * 70 + "\n")
            for entry in result['entries']:
                is_h3c = entry['name'].lower().endswith('.h3c')
                marker = " [KAMPANIA]" if is_h3c else ""
                compressed = "TAK" if entry['size_compressed'] != entry['size_original'] and entry['size_compressed'] > 0 else "NIE"
                f.write(f"{entry['name']:20} rozmiar={entry['size_original']:10} skompresowany={compressed}{marker}\n")

        # Zapisz teksty kampanii
        if result['campaign_texts']:
            all_campaign_texts.extend(result['campaign_texts'])

            # Zapisz do JSON
            json_file = output_dir / f"{filepath.stem}_campaign_texts.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(result['campaign_texts'], f, ensure_ascii=False, indent=2)

            # Zapisz do czytelnego TXT
            txt_file = output_dir / f"{filepath.stem}_campaign_texts.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"Teksty kampanii z {filepath.name}\n")
                f.write("=" * 70 + "\n\n")

                current_source = None
                for i, text_entry in enumerate(result['campaign_texts']):
                    # Nagłówek sekcji dla nowego źródła
                    if text_entry['source'] != current_source:
                        current_source = text_entry['source']
                        f.write(f"\n{'#' * 70}\n")
                        f.write(f"# Źródło: {current_source}\n")
                        f.write(f"{'#' * 70}\n\n")

                    f.write(f"--- [{text_entry['id']}] offset={text_entry['offset']} ---\n")
                    f.write(f"{text_entry['text']}\n\n")

            print(f"  Zapisano {len(result['campaign_texts'])} tekstów do {txt_file.name}")

    # Podsumowanie wszystkich kampanii
    if all_campaign_texts:
        # JSON ze wszystkimi tekstami
        summary_json = output_dir / "_wszystkie_kampanie.json"
        with open(summary_json, 'w', encoding='utf-8') as f:
            json.dump(all_campaign_texts, f, ensure_ascii=False, indent=2)

        # TXT ze wszystkimi tekstami pogrupowanymi
        summary_txt = output_dir / "_wszystkie_kampanie.txt"
        with open(summary_txt, 'w', encoding='utf-8') as f:
            f.write("WSZYSTKIE TEKSTY KAMPANII HEROES OF MIGHT AND MAGIC III\n")
            f.write("=" * 70 + "\n\n")

            # Grupuj po źródle
            by_source = {}
            for text in all_campaign_texts:
                src = text['source']
                if src not in by_source:
                    by_source[src] = []
                by_source[src].append(text)

            for source, texts in sorted(by_source.items()):
                f.write(f"\n{'#' * 70}\n")
                f.write(f"# {source} ({len(texts)} tekstów)\n")
                f.write(f"{'#' * 70}\n\n")

                for text in texts:
                    f.write(f"[{text['id']}] {text['text']}\n\n")

        print(f"\n{'=' * 70}")
        print(f"PODSUMOWANIE:")
        print(f"  Łącznie znaleziono {len(all_campaign_texts)} tekstów kampanii")
        print(f"  Z {len(by_source)} różnych źródeł (plików .h3c)")
        print(f"  Zapisano do: {output_dir}")
        print(f"  Główny plik: _wszystkie_kampanie.txt")


def main():
    parser = argparse.ArgumentParser(
        description='Ekstraktor tekstów kampanii z plików LOD Heroes 3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady użycia:
  python extract_campaign_texts.py "F:\\gry\\Heroes3\\Data"
  python extract_campaign_texts.py "F:\\gry\\Heroes3\\Data\\Woj_bmp.lod" -o wyniki
        """
    )
    parser.add_argument('input', help='Plik .lod lub folder z plikami LOD')
    parser.add_argument('--output', '-o', default='campaign_texts_extracted',
                       help='Folder wyjściowy (domyślnie: campaign_texts_extracted)')

    args = parser.parse_args()
    extract_campaign_texts(args.input, args.output)


if __name__ == '__main__':
    main()
