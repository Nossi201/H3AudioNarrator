#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ekstraktor tekstów fabularnych z plików Heroes of Might and Magic III
Obsługuje pliki .h3m (mapy) i .h3c (kampanie)

Użycie:
    python extract_h3_texts.py <plik_lub_folder> [--output folder_wyjsciowy]
"""

import os
import sys
import gzip
import struct
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, BinaryIO

class H3TextExtractor:
    def __init__(self):
        self.texts = []
        self.current_file = ""

    def read_string(self, f: BinaryIO) -> str:
        """Odczytuje string z pliku H3 (4 bajty długość + dane)"""
        length_data = f.read(4)
        if len(length_data) < 4:
            return ""
        length = struct.unpack('<I', length_data)[0]
        if length == 0 or length > 100000:  # Zabezpieczenie przed błędnymi danymi
            return ""
        data = f.read(length)
        if len(data) < length:
            return ""
        try:
            # Próbuj różne kodowania
            for encoding in ['cp1250', 'cp1252', 'utf-8', 'latin-1']:
                try:
                    return data.decode(encoding)
                except:
                    continue
            return data.decode('latin-1', errors='replace')
        except:
            return ""

    def add_text(self, text: str, context: str, offset: int):
        """Dodaje tekst do listy jeśli jest niepusty i wygląda na tekst fabularny"""
        if not text or len(text.strip()) < 3:
            return

        # Filtruj śmieci - sprawdź czy tekst zawiera głównie drukowalne znaki
        printable_ratio = sum(1 for c in text if c.isprintable() or c in '\n\r\t') / len(text)
        if printable_ratio < 0.9:
            return

        # Dodatkowe filtrowanie znaków kontrolnych i śmieci binarnych
        # Znaki niedrukowalne (poza białymi znakami) to śmieci
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        if control_chars > 0:
            return

        # Odrzuć teksty z dużą ilością znaków specjalnych (typowe dla danych binarnych)
        special_chars = sum(1 for c in text if ord(c) > 127 and ord(c) < 160)
        if len(text) > 0 and special_chars / len(text) > 0.1:
            return

        # Odrzuć teksty które wyglądają na nazwy plików lub ścieżki
        if any(text.strip().lower().endswith(ext) for ext in ['.pcx', '.def', '.wav', '.mp3', '.h3m', '.h3c', '.txt', '.bmp', '.msk']):
            return

        self.texts.append({
            'file': self.current_file,
            'context': context,
            'offset': offset,
            'text': text
        })

    def extract_from_h3m(self, filepath: str) -> List[Dict]:
        """Ekstrahuje teksty z pliku mapy .h3m"""
        self.texts = []
        self.current_file = os.path.basename(filepath)

        try:
            # Pliki H3M są skompresowane gzipem
            with gzip.open(filepath, 'rb') as f:
                self._parse_h3m(f)
        except gzip.BadGzipFile:
            # Może być nieskompresowany
            try:
                with open(filepath, 'rb') as f:
                    self._parse_h3m(f)
            except Exception as e:
                print(f"  Błąd parsowania {filepath}: {e}")
        except Exception as e:
            print(f"  Błąd odczytu {filepath}: {e}")

        return self.texts

    def _parse_h3m(self, f: BinaryIO):
        """Parsuje strukturę pliku H3M"""
        start_pos = f.tell()

        # Nagłówek mapy
        header = f.read(4)
        if len(header) < 4:
            return

        version = struct.unpack('<I', header)[0]
        # Wersje: RoE=0x0E, AB=0x15, SoD=0x1C, WoG=0x33

        # Pomiń niektóre dane nagłówka
        f.read(1)  # has players
        height = struct.unpack('<I', f.read(4))[0]
        f.read(1)  # has underground

        # Nazwa mapy
        offset = f.tell()
        name = self.read_string(f)
        self.add_text(name, "map_name", offset)

        # Opis mapy
        offset = f.tell()
        description = self.read_string(f)
        self.add_text(description, "map_description", offset)

        # Trudność
        f.read(1)

        # Level cap (tylko SoD+)
        if version >= 0x1C:
            f.read(1)

        # Informacje o graczach (8 graczy)
        for player_id in range(8):
            self._parse_player_info(f, version, player_id)

        # Warunki zwycięstwa
        self._parse_victory_condition(f, version)

        # Warunki porażki
        self._parse_loss_condition(f, version)

        # Teams
        f.read(1)  # teams count
        if f.read(1)[0]:  # has teams
            f.read(8)  # team assignments

        # Free heroes
        self._skip_free_heroes(f, version)

        # Prohibited artifacts/spells/skills
        self._skip_prohibitions(f, version)

        # Rumors
        self._parse_rumors(f)

        # Predefined heroes (SoD+)
        if version >= 0x1C:
            self._parse_predefined_heroes(f, version)

        # Pomijamy dane terenu i przechodzimy do obiektów
        # To jest skomplikowane, więc szukamy tekstów heurystycznie
        self._search_for_texts(f)

    def _parse_player_info(self, f: BinaryIO, version: int, player_id: int):
        """Parsuje informacje o graczu"""
        can_human = f.read(1)[0]
        can_ai = f.read(1)[0]

        if not can_human and not can_ai:
            if version >= 0x15:  # AB+
                f.read(1)  # AI behavior
            return

        if version >= 0x15:
            f.read(1)  # AI behavior

        if version >= 0x1C:
            f.read(1)  # allowed alignments set

        f.read(2)  # allowed towns
        f.read(1)  # is town random

        has_main_town = f.read(1)[0]
        if has_main_town:
            if version >= 0x15:
                f.read(1)  # generate hero
                f.read(1)  # generate hero type
            f.read(3)  # town position

        f.read(1)  # random hero
        hero_type = f.read(1)[0]

        if hero_type != 0xFF:
            f.read(1)  # hero portrait
            offset = f.tell()
            hero_name = self.read_string(f)
            self.add_text(hero_name, f"player_{player_id}_hero_name", offset)

        if version >= 0x15:
            f.read(1)  # power placeholder
            hero_count = struct.unpack('<I', f.read(4))[0]
            for _ in range(hero_count):
                f.read(1)  # hero id
                offset = f.tell()
                name = self.read_string(f)
                self.add_text(name, f"player_{player_id}_hero", offset)

    def _parse_victory_condition(self, f: BinaryIO, version: int):
        """Parsuje warunki zwycięstwa"""
        victory_type = f.read(1)[0]

        if victory_type == 0xFF:  # Standard
            return

        f.read(1)  # allow normal victory
        f.read(1)  # applies to AI

        if victory_type == 0:  # Acquire artifact
            if version >= 0x1C:
                f.read(2)
            else:
                f.read(1)
        elif victory_type == 1:  # Accumulate creatures
            if version >= 0x1C:
                f.read(2)
            else:
                f.read(1)
            f.read(4)  # amount
        elif victory_type == 2:  # Accumulate resources
            f.read(1)  # resource type
            f.read(4)  # amount
        elif victory_type == 3:  # Upgrade town
            f.read(3)  # position
            f.read(1)  # hall level
            f.read(1)  # castle level
        elif victory_type == 4:  # Build grail
            f.read(3)  # position (can be 0xFF for any)
        elif victory_type == 5:  # Defeat hero
            f.read(3)  # position
        elif victory_type == 6:  # Capture town
            f.read(3)  # position
        elif victory_type == 7:  # Defeat monster
            f.read(3)  # position
        elif victory_type == 8:  # Flag dwellings
            pass
        elif victory_type == 9:  # Flag mines
            pass
        elif victory_type == 10:  # Transport artifact
            f.read(1)  # artifact
            f.read(3)  # destination

    def _parse_loss_condition(self, f: BinaryIO, version: int):
        """Parsuje warunki porażki"""
        loss_type = f.read(1)[0]

        if loss_type == 0xFF:  # Standard
            return

        if loss_type == 0:  # Lose town
            f.read(3)  # position
        elif loss_type == 1:  # Lose hero
            f.read(3)  # position
        elif loss_type == 2:  # Time limit
            f.read(2)  # days

    def _skip_free_heroes(self, f: BinaryIO, version: int):
        """Pomija sekcję free heroes"""
        if version >= 0x15:
            count = f.read(1)[0]
            for _ in range(count):
                f.read(1)  # hero id
                f.read(1)  # portrait
                offset = f.tell()
                name = self.read_string(f)
                self.add_text(name, "free_hero_name", offset)
                f.read(1)  # players

        if version >= 0x1C:
            f.read(20)  # reserved

    def _skip_prohibitions(self, f: BinaryIO, version: int):
        """Pomija sekcje zakazów"""
        if version >= 0x1C:
            f.read(20)  # artifacts (SoD: 18 + padding)
            f.read(4)   # spells
            f.read(4)   # skills

    def _parse_rumors(self, f: BinaryIO):
        """Parsuje plotki"""
        count = struct.unpack('<I', f.read(4))[0]
        for i in range(min(count, 100)):  # Limit dla bezpieczeństwa
            offset = f.tell()
            name = self.read_string(f)
            self.add_text(name, f"rumor_{i}_name", offset)

            offset = f.tell()
            text = self.read_string(f)
            self.add_text(text, f"rumor_{i}_text", offset)

    def _parse_predefined_heroes(self, f: BinaryIO, version: int):
        """Parsuje predefiniowanych bohaterów"""
        for hero_id in range(156):  # Max heroes in SoD
            has_custom = f.read(1)[0]
            if not has_custom:
                continue

            has_exp = f.read(1)[0]
            if has_exp:
                f.read(4)  # experience

            has_skills = f.read(1)[0]
            if has_skills:
                count = struct.unpack('<I', f.read(4))[0]
                f.read(count * 2)  # skills

            has_artifacts = f.read(1)[0]
            if has_artifacts:
                # Skomplikowane - pomijamy
                self._skip_artifact_set(f, version)

            has_bio = f.read(1)[0]
            if has_bio:
                offset = f.tell()
                bio = self.read_string(f)
                self.add_text(bio, f"hero_{hero_id}_bio", offset)

            f.read(1)  # gender

            has_spells = f.read(1)[0]
            if has_spells:
                f.read(9)  # spells bitmask

            has_primary = f.read(1)[0]
            if has_primary:
                f.read(4)  # primary skills

    def _skip_artifact_set(self, f: BinaryIO, version: int):
        """Pomija zestaw artefaktów bohatera"""
        # Head, shoulders, neck, right_hand, left_hand, torso, right_ring, left_ring
        # feet, misc1-5, ballista, ammo_cart, first_aid, catapult, spell_book
        slot_count = 19 if version >= 0x1C else 16
        for _ in range(slot_count):
            if version >= 0x1C:
                f.read(2)  # artifact id (16-bit)
            else:
                f.read(1)  # artifact id (8-bit)

        # Backpack
        count = struct.unpack('<H', f.read(2))[0]
        for _ in range(count):
            if version >= 0x1C:
                f.read(2)
            else:
                f.read(1)

    def _search_for_texts(self, f: BinaryIO):
        """Heurystyczne wyszukiwanie tekstów w reszcie pliku"""
        # Zapisz pozycję
        current_pos = f.tell()

        # Czytaj resztę pliku
        data = f.read()

        # Szukaj wzorców stringów H3 (4 bajty długość + tekst)
        i = 0
        text_id = 0
        while i < len(data) - 10:
            # Sprawdź czy to może być długość stringa
            if i + 4 > len(data):
                break

            length = struct.unpack('<I', data[i:i+4])[0]

            # Rozsądna długość dla tekstu fabularnego
            if 10 < length < 5000 and i + 4 + length <= len(data):
                text_data = data[i+4:i+4+length]

                # Sprawdź czy to wygląda na tekst
                try:
                    text = text_data.decode('cp1250', errors='strict')
                    # Sprawdź proporcję drukowalnych znaków
                    printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t ')
                    if printable / len(text) > 0.92:
                        # Dodatkowe sprawdzenie - czy nie ma znaków kontrolnych
                        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t ')
                        # Sprawdź znaki z zakresu 128-159 (znaki kontrolne w Windows-1250)
                        special_chars = sum(1 for c in text if 128 <= ord(c) < 160)
                        if control_chars == 0 and special_chars / len(text) < 0.05:
                            self.add_text(text, f"object_text_{text_id}", current_pos + i)
                            text_id += 1
                            i += 4 + length
                            continue
                except:
                    pass

            i += 1

    def extract_from_h3c(self, filepath: str) -> List[Dict]:
        """Ekstrahuje teksty z pliku kampanii .h3c"""
        self.texts = []
        self.current_file = os.path.basename(filepath)

        try:
            with gzip.open(filepath, 'rb') as f:
                self._parse_h3c(f)
        except gzip.BadGzipFile:
            try:
                with open(filepath, 'rb') as f:
                    self._parse_h3c(f)
            except Exception as e:
                print(f"  Błąd parsowania {filepath}: {e}")
        except Exception as e:
            print(f"  Błąd odczytu {filepath}: {e}")

        return self.texts

    def _parse_h3c(self, f: BinaryIO):
        """Parsuje strukturę pliku kampanii H3C"""
        # Wersja kampanii
        version = struct.unpack('<I', f.read(4))[0]

        # ID kampanii
        f.read(1)

        # Nazwa kampanii
        offset = f.tell()
        name = self.read_string(f)
        self.add_text(name, "campaign_name", offset)

        # Opis kampanii
        offset = f.tell()
        description = self.read_string(f)
        self.add_text(description, "campaign_description", offset)

        # Różność muzyczna
        if version > 1:
            f.read(1)

        # Liczba scenariuszy
        scenario_count = f.read(1)[0]

        for i in range(scenario_count):
            # Nazwa scenariusza
            offset = f.tell()
            scenario_name = self.read_string(f)
            self.add_text(scenario_name, f"scenario_{i}_name", offset)

            # Opis scenariusza
            offset = f.tell()
            scenario_desc = self.read_string(f)
            self.add_text(scenario_desc, f"scenario_{i}_description", offset)

            # Pomiń resztę danych scenariusza
            # (skomplikowane, używamy heurystyki)

        # Szukaj więcej tekstów heurystycznie
        self._search_for_texts(f)


def extract_texts(input_path: str, output_dir: str):
    """Główna funkcja ekstrakcji"""
    extractor = H3TextExtractor()
    all_texts = []

    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Zbierz pliki do przetworzenia
    files_to_process = []
    if input_path.is_file():
        files_to_process.append(input_path)
    else:
        files_to_process.extend(input_path.rglob('*.h3m'))
        files_to_process.extend(input_path.rglob('*.h3c'))

    print(f"Znaleziono {len(files_to_process)} plików do przetworzenia...")

    for filepath in files_to_process:
        print(f"Przetwarzanie: {filepath.name}")

        if filepath.suffix.lower() == '.h3m':
            texts = extractor.extract_from_h3m(str(filepath))
        elif filepath.suffix.lower() == '.h3c':
            texts = extractor.extract_from_h3c(str(filepath))
        else:
            continue

        if texts:
            all_texts.extend(texts)
            print(f"  Znaleziono {len(texts)} tekstów")

            # Zapisz teksty dla tego pliku
            output_file = output_dir / f"{filepath.stem}_texts.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(texts, f, ensure_ascii=False, indent=2)

            # Zapisz też w formacie łatwym do edycji
            txt_file = output_dir / f"{filepath.stem}_texts.txt"
            with open(txt_file, 'w', encoding='utf-8') as f:
                for i, text_entry in enumerate(texts):
                    f.write(f"=== [{i}] {text_entry['context']} ===\n")
                    f.write(f"{text_entry['text']}\n")
                    f.write("\n")

    # Zapisz wszystkie teksty razem
    if all_texts:
        all_texts_file = output_dir / "_all_texts.json"
        with open(all_texts_file, 'w', encoding='utf-8') as f:
            json.dump(all_texts, f, ensure_ascii=False, indent=2)

        print(f"\nŁącznie znaleziono {len(all_texts)} tekstów")
        print(f"Zapisano do: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Ekstraktor tekstów fabularnych z Heroes 3')
    parser.add_argument('input', help='Plik .h3m/.h3c lub folder z plikami')
    parser.add_argument('--output', '-o', default='extracted_texts', help='Folder wyjściowy')

    args = parser.parse_args()

    extract_texts(args.input, args.output)


if __name__ == '__main__':
    main()
