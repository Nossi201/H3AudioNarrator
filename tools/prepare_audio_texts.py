#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Przygotowanie tekstów kampanii do generowania audio z ElevenLabs.

NOWA LOGIKA:
- Tekst BEZ cudzysłowów = tylko narrator (pusta tablica głosów)
- Tekst Z cudzysłowami = narrator + dialogi NPC/Tarnum
- Każdy cytat "" wymaga osobnego głosu (tablica może mieć wiele elementów)
- Plik edycji ma format: ID | [głosy] | TEKST

Głosy:
- narrator: Czyta wszystko poza cudzysłowami (domyślny)
- tarnum: Wypowiedzi Tarnuma w cudzysłowach
- npc_m: Męskie postacie NPC w cudzysłowach
- npc_f: Żeńskie postacie NPC w cudzysłowach
- skip: Tytuły, krótkie etykiety (pomijane w audio)
"""

import json
import re
import os
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


# Konfiguracja głosów
VOICES = {
    'narrator': '0el4HQ5fH8KITMM7DKzD',
    'tarnum': 'o2xdfKUpc1Bwq7RchZuW',
    'npc_m': 'XoHJ8hwSLOtb2sXYdAzv',
    'npc_f': 'N0GCuK2B0qwWozQNTS8F',
    'skip': None  # Pomijane
}


def find_quoted_segments(text: str) -> List[Tuple[int, int, str]]:
    """
    Znajduje wszystkie segmenty w cudzysłowach.
    Zwraca: [(start, end, treść), ...]
    """
    pattern = r'"([^"]+)"'
    segments = []
    for match in re.finditer(pattern, text):
        segments.append((match.start(), match.end(), match.group(1)))
    return segments


def classify_text_new(text: str, text_id: int) -> Dict:
    """
    Klasyfikuje tekst według nowej logiki.

    Zwraca:
    {
        'type': 'narrator_only' | 'mixed' | 'skip',
        'quotes': [{'text': ..., 'voice': ''}, ...],  # puste voice = do ręcznego
        'needs_manual': True/False
    }
    """
    text_stripped = text.strip()

    # === SKIP: Tytuły i krótkie etykiety ===
    if len(text_stripped) < 50 and '.' not in text_stripped and '"' not in text:
        return {
            'type': 'skip',
            'quotes': [],
            'needs_manual': False
        }

    # === Znajdź cytaty ===
    quotes = find_quoted_segments(text)

    if not quotes:
        # Brak cudzysłowów = tylko narrator
        return {
            'type': 'narrator_only',
            'quotes': [],
            'needs_manual': False
        }

    # === Jest jeden lub więcej cytatów ===
    quote_info = []
    for start, end, quote_text in quotes:
        # Próba automatycznego przypisania głosu
        voice = auto_detect_voice(text, quote_text, start)
        quote_info.append({
            'text': quote_text[:50] + ('...' if len(quote_text) > 50 else ''),
            'voice': voice  # '' = wymaga ręcznego przypisania
        })

    needs_manual = any(q['voice'] == '' for q in quote_info)

    return {
        'type': 'mixed',
        'quotes': quote_info,
        'needs_manual': needs_manual
    }


def auto_detect_voice(full_text: str, quote_text: str, quote_start: int) -> str:
    """
    Próbuje automatycznie wykryć głos dla cytatu.
    Zwraca: 'tarnum', 'npc_m', 'npc_f' lub '' (pusty = wymaga ręcznego)
    """
    quote_lower = quote_text.lower()
    text_before = full_text[:quote_start].lower()

    # Sprawdź czy to Tarnum mówi
    tarnum_markers = [
        'jestem tarnum', 'ja, tarnum', 'mój lud', 'moją armię', 'mojej armii',
        'moi ludzie', 'moich ludzi', 'poprowadzę', 'zdobędę', 'zniszczę',
        'nie pozwolę', 'muszę', 'moje zwycięstwo', 'moja zemsta',
        'przysiągłem', 'obiecałem', 'mój miecz', 'moja horda',
        'będę walczył', 'nie spocznę', 'przysięgam', 'ja sam',
    ]

    if any(marker in quote_lower for marker in tarnum_markers):
        return 'tarnum'

    # Sprawdź czy przed cytatem jest wzmianka o kobiecie
    female_speakers = [
        'królowa', 'kapłanka', 'czarodziejka', 'wiedźma', 'wróżka',
        'kobieta', 'dziewczyna', 'matka', 'siostra', 'córka',
        'yalla', 'ona mówi', 'ona powiedziała', 'odpowiada kobieta',
    ]

    # Sprawdź ostatnie 100 znaków przed cytatem
    text_context = text_before[-100:] if len(text_before) > 100 else text_before
    if any(marker in text_context for marker in female_speakers):
        return 'npc_f'

    # Domyślnie - pusty (wymaga ręcznego przypisania)
    # Można zmienić na 'npc_m' jeśli chcesz domyślnie męski głos
    return ''


def process_campaign(input_file: str, source_filter: str = None) -> List[Dict]:
    """
    Przetwarza plik kampanii i klasyfikuje teksty.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filtruj po źródle jeśli podano
    if source_filter:
        data = [t for t in data if source_filter in t.get('source', '')]

    # Klasyfikuj każdy tekst
    results = []
    for t in data:
        text = t['text']
        text_id = t.get('id', 0)
        classification = classify_text_new(text, text_id)

        results.append({
            'id': text_id,
            'source': t.get('source', ''),
            'offset': t.get('offset', 0),
            'text': text,
            'classification': classification,
            'chars': len(text)
        })

    return results


def print_summary(texts: List[Dict]):
    """Wyświetla podsumowanie klasyfikacji"""
    narrator_only = sum(1 for t in texts if t['classification']['type'] == 'narrator_only')
    mixed = sum(1 for t in texts if t['classification']['type'] == 'mixed')
    skip = sum(1 for t in texts if t['classification']['type'] == 'skip')
    needs_manual = sum(1 for t in texts if t['classification']['needs_manual'])

    total_quotes = sum(len(t['classification']['quotes']) for t in texts)
    auto_assigned = sum(
        sum(1 for q in t['classification']['quotes'] if q['voice'] != '')
        for t in texts
    )

    print("\n" + "="*60)
    print("PODSUMOWANIE KLASYFIKACJI")
    print("="*60)
    print(f"Tylko narrator (bez dialogów):  {narrator_only:4} tekstów")
    print(f"Mieszane (narrator + dialogi):  {mixed:4} tekstów")
    print(f"Pominięte (tytuły/etykiety):    {skip:4} tekstów")
    print("-"*60)
    print(f"Łącznie cytatów w cudzysłowach: {total_quotes:4}")
    print(f"  - automatycznie przypisane:   {auto_assigned:4}")
    print(f"  - wymaga ręcznego przypisania:{total_quotes - auto_assigned:4}")
    print("-"*60)
    print(f"Teksty wymagające edycji:       {needs_manual:4}")
    print("="*60)

    # Policz znaki
    chars_audio = sum(t['chars'] for t in texts if t['classification']['type'] != 'skip')
    print(f"\nZnaków do audio: {chars_audio:,}")


def clean_text_for_tts(text: str) -> str:
    """
    Czyści tekst do syntezatora mowy.

    ElevenLabs dobrze interpretuje:
    - Kropki, przecinki, wykrzykniki - naturalne pauzy
    - Znaki zapytania - intonacja pytająca
    - Wielokropek (...) - dłuższa pauza

    Problematyczne:
    - \\n (nowa linia) - zamień na spację lub pauzę
    - Tabulatory - usuń
    - Wielokrotne spacje - zamień na pojedyncze
    """
    # Zamień \n na spację (lub możesz użyć "..." dla pauzy)
    text = text.replace('\n', ' ')

    # Usuń tabulatory
    text = text.replace('\t', ' ')

    # Usuń wielokrotne spacje
    text = re.sub(r' +', ' ', text)

    return text.strip()


def save_results(texts: List[Dict], output_dir: str, base_name: str):
    """Zapisuje wyniki do plików"""
    os.makedirs(output_dir, exist_ok=True)

    # 1. Pełny JSON z klasyfikacją
    full_path = os.path.join(output_dir, f"{base_name}_classified.json")
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)
    print(f"\nZapisano: {full_path}")

    # 2. Tylko teksty do audio (bez skip)
    audio_texts = [t for t in texts if t['classification']['type'] != 'skip']
    audio_path = os.path.join(output_dir, f"{base_name}_audio.json")
    with open(audio_path, 'w', encoding='utf-8') as f:
        json.dump(audio_texts, f, ensure_ascii=False, indent=2)
    print(f"Zapisano: {audio_path}")

    # 3. Plik do ręcznej edycji - NOWY FORMAT
    edit_path = os.path.join(output_dir, f"{base_name}_edit.txt")
    with open(edit_path, 'w', encoding='utf-8') as f:
        f.write("# PLIK DO RĘCZNEJ EDYCJI GŁOSÓW\n")
        f.write("#" + "="*69 + "\n")
        f.write("# Format: ID | [głosy] | TEKST\n")
        f.write("#\n")
        f.write("# Głosy dla cytatów: tarnum, npc_m, npc_f\n")
        f.write("# Pusta tablica [] = tylko narrator (brak dialogów)\n")
        f.write("# Tablica z \"\" = wymaga ręcznego przypisania głosu\n")
        f.write("#\n")
        f.write("# Przykłady:\n")
        f.write('#   5|[]|Tekst bez dialogów - tylko narrator\n')
        f.write('#   6|["npc_m"]|Narrator mówi: "cytat jednego NPC"\n')
        f.write('#   7|["npc_m","npc_f"]|Ona: "cześć" On: "witaj"\n')
        f.write('#   8|[""]|Tekst z cytatem - WYMAGA EDYCJI!\n')
        f.write("#\n")
        f.write("# SKIP - pomijane w generowaniu audio\n")
        f.write("#" + "="*69 + "\n\n")

        for t in texts:
            cls = t['classification']
            text_clean = t['text'].replace('\n', '\\n').replace('\t', '\\t')

            if cls['type'] == 'skip':
                # Zakomentowane - pominięte
                f.write(f"# SKIP: {t['id']}|[]|{text_clean[:60]}...\n")

            elif cls['type'] == 'narrator_only':
                # Pusta tablica - tylko narrator
                f.write(f"{t['id']}|[]|{text_clean}\n")

            else:  # mixed
                # Tablica z głosami dla każdego cytatu
                voices = [q['voice'] if q['voice'] else '' for q in cls['quotes']]
                voices_str = json.dumps(voices, ensure_ascii=False)

                # Oznacz czy wymaga edycji
                if cls['needs_manual']:
                    f.write(f"# EDYTUJ: \n")
                f.write(f"{t['id']}|{voices_str}|{text_clean}\n")

    print(f"Zapisano: {edit_path} (do ręcznej edycji)")

    # 4. Plik z tekstami do TTS (oczyszczone)
    tts_path = os.path.join(output_dir, f"{base_name}_tts_ready.json")
    tts_texts = []
    for t in texts:
        if t['classification']['type'] != 'skip':
            tts_texts.append({
                'id': t['id'],
                'text_original': t['text'],
                'text_clean': clean_text_for_tts(t['text']),
                'voices': [q['voice'] for q in t['classification']['quotes']]
            })
    with open(tts_path, 'w', encoding='utf-8') as f:
        json.dump(tts_texts, f, ensure_ascii=False, indent=2)
    print(f"Zapisano: {tts_path} (teksty oczyszczone dla TTS)")


def main():
    parser = argparse.ArgumentParser(
        description='Przygotowanie tekstów kampanii do audio',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python prepare_audio_texts.py chronicles_voiceover/campaign_extracted/Woj_bmp_campaign_texts.json --source ab.h3c
  python prepare_audio_texts.py chronicles_voiceover/campaign_extracted/Woj_bmp_campaign_texts.json -o chronicles_voiceover/audio_prepared
        """
    )

    parser.add_argument('input', help='Plik JSON z tekstami kampanii')
    parser.add_argument('--source', '-s', help='Filtruj po źródle (np. ab.h3c)')
    parser.add_argument('--output', '-o', default='chronicles_voiceover/audio_prepared', help='Katalog wyjściowy')
    parser.add_argument('--preview', action='store_true', help='Tylko podgląd, bez zapisywania')

    args = parser.parse_args()

    # Nazwa bazowa z pliku wejściowego
    base_name = Path(args.input).stem
    if args.source:
        base_name += "_" + args.source.replace('.h3c', '')

    print(f"Przetwarzanie: {args.input}")
    if args.source:
        print(f"Filtr źródła: {args.source}")

    # Przetwórz
    texts = process_campaign(args.input, args.source)

    # Podsumowanie
    print_summary(texts)

    # Przykładowe teksty wymagające edycji
    needs_edit = [t for t in texts if t['classification']['needs_manual']][:5]
    if needs_edit:
        print("\n" + "="*60)
        print("PRZYKŁADY WYMAGAJĄCE RĘCZNEJ EDYCJI")
        print("="*60)
        for t in needs_edit:
            text_short = t['text'][:80].replace('\n', ' ')
            quotes = t['classification']['quotes']
            print(f"\n[{t['id']}] {len(quotes)} cytat(ów):")
            print(f"  {text_short}...")
            for i, q in enumerate(quotes):
                print(f"    Cytat {i+1}: \"{q['text']}\" -> głos: ???")

    # Zapisz
    if not args.preview:
        save_results(texts, args.output, base_name)

    # Info o \n
    print("\n" + "="*60)
    print("INFO O ZNAKACH SPECJALNYCH")
    print("="*60)
    print("ElevenLabs dobrze interpretuje:")
    print("  . , ! ? - naturalne pauzy i intonacja")
    print("  ... (wielokropek) - dłuższa pauza")
    print("")
    print("Znaki \\n (nowa linia) zostały zamienione na spacje")
    print("w pliku _tts_ready.json")


if __name__ == '__main__':
    main()
