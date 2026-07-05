#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje text_map.txt z kolumną filtra mapy.

Dla każdego wpisu z text_map.txt ustala na której mapie
(pliku .h3m wewnątrz kampanii) dany tekst się pojawia,
a następnie zapisuje wynik jako text_map_with_filter.txt.

Nazwa mapy w kolumnie filtra to PRAWDZIWY tytuł scenariusza odczytany
wprost z nagłówka osadzonej mapy H3M (to samo pole H3String mapName,
które silnik zwraca w runtime przez H3Main::mapInfo.mapName) - a NIE
wewnętrzny kod ("PustkowiaA" itp.). Bez tego MapFilterMatches() w C++
nigdy nie mogłoby dopasować filtra do rzeczywistej nazwy mapy w grze.

Format wyjściowy:
    kod_id|prefix_tekstu|prawdziwa_nazwa_mapy
    (kod_id = "woj_XXX" - kompozytowy klucz zgodny z nazwą pliku audio)

Użycie:
    py -3 generate_text_map_with_filter.py
"""

import sys
import struct
import gzip
import zlib
import json
import os
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────────────────────
LOD_PATH       = r"F:\gry\h3-Chro-Hdmod(modowanie)\HoMM 3 Complete\Data\Woj_bmp.lod"
H3C_NAME       = "ab.h3c"
TEXT_MAP_IN    = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\audio_woj_campaign\text_map.txt"
CAMPAIGN_JSON  = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\campaign_extracted\Woj_bmp_campaign_texts.json"
OUTPUT_FILE    = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\audio_woj_campaign\text_map_with_filter.txt"
DEBUG_FILE     = r"F:\gry\h3-Chro-Hdmod(modowanie)\plugin\H3ButtonPlugin\tools\audio_woj_campaign\text_map_filter_debug.txt"

# ─────────────────────────────────────────────────────────────
# H3M BOUNDARIES – wykryte empirycznie przez skanowanie H3M
# version=28 + has_players + dimension + has_underground + H3String mapName.
#
# Nazwy w komentarzach to tylko etykiety dla człowieka (nieużywane w output) -
# prawdziwy tytuł scenariusza jest czytany w runtime bezpośrednio z H3String
# mapName pod tym samym offsetem (patrz read_real_map_name), bo to jest
# dokładnie to samo pole, które silnik zwraca przez H3Main::mapInfo.mapName.
#
# Jak zaktualizować: odpal skrypt z --scan i sprawdź output.
# Format: (offset_start, "etykieta_pomocnicza")
# ─────────────────────────────────────────────────────────────
H3M_BOUNDARIES = [
    (    0,      ""),           # nagłówek H3C (przed pierwszą mapą) = globalny
    (43118,      "PustkowiaA"), # Król przestępca
    (77260,      "PustkowiaB"), # Ultimatum
    (114945,     "PustkowiaC"), # Bitwa o bagna
    (207247,     "PustkowiaD"), # Bitwa o Blanki
    (380193,     "PustkowiaE"), # W pułapce!
    (470141,     "PustkowiaF"), # Ogniem i mieczem
    (509582,     "PustkowiaG"), # Steelhorn  (do ~612000)
    (612031,     "PustkowiaH"), # ostatnia mapa (po dużej przerwie)
]


def read_h3string(data: bytes, offset: int):
    """Czyta H3String (int32 dlugosc + tresc) z podanego offsetu.
       Zwraca (tekst, offset_za_stringiem) albo (None, offset) gdy dlugosc
       wyglada na bezsensowna (offset nie wskazuje na prawdziwy H3String)."""
    length = struct.unpack('<i', data[offset:offset + 4])[0]
    offset += 4
    if length <= 0 or length > 200 or offset + length > len(data):
        return None, offset
    raw = data[offset:offset + length]
    text = raw.decode('cp1250', errors='strict')
    return text, offset + length


def read_real_map_name(data: bytes, h3m_offset: int) -> str:
    """
    Czyta prawdziwa nazwe scenariusza z naglowka osadzonej mapy H3M w .h3c,
    zaczynajac od h3m_offset (offset ustalony empirycznie w H3M_BOUNDARIES).
    Uklad: version(4) + has_players(1) + dimension(4) + has_underground(1),
    potem H3String mapName - to samo pole co H3Main::mapInfo.mapName w runtime.
    Zwraca "" (zamiast rzucac wyjatek) gdy offset nie wyglada na poprawny
    naglowek H3M - lepiej dostac pusty mapFilter (= dopasuj wszedzie) niz
    wywalic cala generacje przez jeden niepewny offset.
    """
    pos = h3m_offset + 4 + 1 + 4 + 1  # version + has_players + dimension + has_underground
    try:
        name, _ = read_h3string(data, pos)
    except UnicodeDecodeError:
        return ""
    return name.strip() if name is not None else ""


# ─────────────────────────────────────────────────────────────
# KROK 1: Wyciągnij ab.h3c z LOD i zdekompresuj
# ─────────────────────────────────────────────────────────────

def extract_from_lod(lod_path: str, target_name: str) -> bytes:
    with open(lod_path, 'rb') as f:
        magic = f.read(4)
        assert magic == b'LOD\x00', f"Nieprawidłowy nagłówek LOD: {magic}"
        f.read(4)
        file_count = struct.unpack('<I', f.read(4))[0]
        f.read(80)

        entries = []
        for _ in range(file_count):
            name   = f.read(16).split(b'\x00')[0].decode('latin-1')
            offset = struct.unpack('<I', f.read(4))[0]
            size_o = struct.unpack('<I', f.read(4))[0]
            f.read(4)
            size_c = struct.unpack('<I', f.read(4))[0]
            entries.append((name, offset, size_o, size_c))

        for name, offset, size_o, size_c in entries:
            if name.lower() == target_name.lower():
                f.seek(offset)
                data = f.read(size_o)
                if data[:2] == b'\x1f\x8b':
                    data = gzip.decompress(data)
                return data

    raise FileNotFoundError(f"Nie znaleziono '{target_name}' w LOD: {lod_path}")


# ─────────────────────────────────────────────────────────────
# KROK 2: Zbuduj zakresy offsetów z H3M_BOUNDARIES
# ─────────────────────────────────────────────────────────────

def build_map_ranges(data: bytes):
    """
    Buduje listę (prawdziwa_nazwa_mapy, range_start, range_end) z H3M_BOUNDARIES.
    Koniec każdego zakresu = początek następnego (lub len(data) dla ostatniego).
    Nazwa dla start>0 jest czytana z H3String w nagłówku H3M (read_real_map_name),
    NIE z etykiety w H3M_BOUNDARIES - dzięki temu zgadza się z GetCurrentMapName()
    zwracanym przez silnik w runtime.
    """
    ranges = []
    for i, (start, label) in enumerate(H3M_BOUNDARIES):
        end = H3M_BOUNDARIES[i + 1][0] if i + 1 < len(H3M_BOUNDARIES) else len(data)
        name = read_real_map_name(data, start) if start > 0 else ""
        ranges.append((name, start, end))
    return ranges


# ─────────────────────────────────────────────────────────────
# KROK 5: Wczytaj text_map.txt i JSON z offsetami
# ─────────────────────────────────────────────────────────────

def load_text_map(path):
    entries = []
    with open(path, encoding='cp1250', errors='replace') as f:
        for line in f:
            line = line.rstrip('\r\n')
            if not line or line.startswith('#'):
                continue
            parts = line.split('|', 2)
            if len(parts) >= 2:
                text_id = int(parts[0])
                prefix  = parts[1]
                entries.append({'id': text_id, 'prefix': prefix})
    return entries


def load_campaign_json(path):
    """Zwraca słownik prefix_tekstu -> offset_w_h3c"""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    # Buduj mapę: pierwsze 40 znaków tekstu -> offset
    by_prefix = {}
    for e in data:
        key = e['text'][:40]
        by_prefix[key] = e['offset']
    return by_prefix


# ─────────────────────────────────────────────────────────────
# KROK 6: Dopasuj każdy tekst do mapy
# ─────────────────────────────────────────────────────────────

def find_map_for_offset(offset: int, map_ranges):
    """
    Zwraca nazwę mapy dla danego offsetu.
    Texty przed pierwszym H3M lub nienależące do żadnego zakresu
    -> zwraca '' (= graj na wszystkich mapach).
    """
    for (map_name, r_start, r_end) in map_ranges:
        if r_start <= offset < r_end:
            return map_name
    return ''  # przed H3M lub poza – globalny


def match_prefix_to_offset(prefix: str, campaign_json_by_prefix):
    """Szuka pasującego wpisu w JSON po prefiksie (pierwsze 30 znaków)."""
    for key_len in (40, 30, 20, 15, 10):
        short_prefix = prefix[:key_len]
        for json_key, offset in campaign_json_by_prefix.items():
            if json_key[:key_len] == short_prefix:
                return offset
    return None


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("generate_text_map_with_filter.py")
    print("=" * 60)

    # 1. Wyciągnij i zdekompresuj H3C (potrzebne do weryfikacji rozmiaru i odczytu nazw map)
    print(f"\n[1] Wczytuję {H3C_NAME} z LOD...")
    h3c_data = extract_from_lod(LOD_PATH, H3C_NAME)
    print(f"  Rozmiar po dekompresji: {len(h3c_data)} bajtów")

    # 2. Zakresy offsetów z H3M_BOUNDARIES + prawdziwe nazwy map z naglowkow H3M
    map_ranges = build_map_ranges(h3c_data)
    print(f"\n[2] Zakresy H3M (prawdziwe nazwy scenariuszy):")
    console_enc = sys.stdout.encoding or 'cp1250'
    for (mn, rs, re) in map_ranges:
        label = mn if mn else "(naglowek H3C = globalny / nie rozpoznano)"
        # Konsola Windows moze nie obslugiwac kazdego znaku - plik wyjsciowy to i tak UTF-8
        safe_label = label.encode(console_enc, errors='replace').decode(console_enc, errors='replace')
        print(f"    '{safe_label}': {rs} - {re}")

    # 3. Wczytaj text_map.txt i JSON
    print(f"\n[3] Wczytuję text_map.txt...")
    text_entries = load_text_map(TEXT_MAP_IN)
    print(f"  Wpisów: {len(text_entries)}")

    print(f"\n[4] Wczytuję campaign JSON...")
    json_by_prefix = load_campaign_json(CAMPAIGN_JSON)
    print(f"  Wpisów w JSON: {len(json_by_prefix)}")

    # 4. Dopasuj teksty do map
    print(f"\n[5] Dopasowuję teksty do map...")
    results    = []
    debug_lines = []
    unmatched  = 0

    for entry in text_entries:
        prefix  = entry['prefix']
        text_id = entry['id']

        offset = match_prefix_to_offset(prefix, json_by_prefix)
        if offset is None:
            filter_val = ''
            status     = 'BRAK_W_JSON'
            unmatched += 1
        else:
            map_name   = find_map_for_offset(offset, map_ranges)
            filter_val = map_name  # już bez .h3m (z H3M_BOUNDARIES)
            status     = f"off={offset}"

        results.append({'id': text_id, 'prefix': prefix, 'filter': filter_val})
        debug_lines.append(f"{text_id:4d}|{status:16s}|'{filter_val:12s}'|{prefix[:50]}")

    print(f"  Niedopasowanych: {unmatched}/{len(text_entries)}")

    from collections import Counter
    cnt = Counter(r['filter'] for r in results)
    print(f"\n  Rozkład wg filtrów:")
    for k, v in sorted(cnt.items()):
        label = k if k else "(globalny)"
        print(f"    {label}: {v} tekstów")

    # 5. Zapisz wyniki
    print(f"\n[6] Zapisuję {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# text_map.txt z filtrem mapy\n")
        f.write("# Format: woj_XXX|prefix_tekstu|nazwa_mapy  (puste = wszystkie mapy)\n")
        f.write("# woj_XXX = kompozytowy kod ID (kampania_lokalneId), zgodny z nazwa pliku audio woj_XXX.mp3\n")
        f.write("# Wygenerowane przez generate_text_map_with_filter.py\n\n")
        for r in results:
            line = f"woj_{r['id']:03d}|{r['prefix']}"
            if r['filter']:
                line += f"|{r['filter']}"
            f.write(line + "\n")

    print(f"[6] Zapisuję debug: {DEBUG_FILE}...")
    with open(DEBUG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"{'id':>4}|{'offset_status':16}|{'filter':14}|prefix\n")
        f.write("-" * 90 + "\n")
        for line in debug_lines:
            f.write(line + "\n")

    print(f"\nGotowe!")
    print(f"  {OUTPUT_FILE}")
    print(f"  {DEBUG_FILE}")


if __name__ == '__main__':
    main()
