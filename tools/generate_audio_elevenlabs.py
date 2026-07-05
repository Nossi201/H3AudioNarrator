#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator audio z tekstów Heroes 3 przy użyciu ElevenLabs API.

Wymagania:
    pip install elevenlabs

Użycie:
    python generate_audio_elevenlabs.py <plik.json> --api-key YOUR_API_KEY [--voice VOICE_ID]

Przykład:
    python generate_audio_elevenlabs.py campaign_extracted/Woj_bmp_campaign_texts.json --api-key sk-... --voice pMsXgVXv3BLzUgSXRplE
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from typing import List, Dict, Optional

# Sprawdź czy elevenlabs jest zainstalowane
try:
    from elevenlabs import ElevenLabs, VoiceSettings
except ImportError:
    print("Błąd: Zainstaluj pakiet elevenlabs:")
    print("  pip install elevenlabs")
    sys.exit(1)


# Popularne głosy ElevenLabs (Multilingual v2 - dobre dla polskiego)
RECOMMENDED_VOICES = {
    "Adam": "pNInz6obpgDQGcFmaJgB",      # Głęboki, męski
    "Antoni": "ErXwobaYiN019PkySvjV",    # Męski, przyjazny
    "Arnold": "VR6AewLTigWG4xSOukaG",    # Męski, narratorski
    "Callum": "N2lVS1w4EtoT3dr4eOWO",    # Męski, spokojny
    "Charlie": "IKne3meq5aSn9XLyUdCD",   # Męski, naturalny
    "Clyde": "2EiwWnXFnvU5JabPnv8n",     # Męski, ciepły
    "Daniel": "onwK4e9ZLuTAKqWW03F9",    # Męski, brytyjski
    "Dave": "CYw3kZ02Hs0563khs1Fj",      # Męski, konwersacyjny
    "Domi": "AZnzlk1XvdvUeBnXmlld",      # Żeński, mocny
    "Dorothy": "ThT5KcBeYPX3keUQqHPh",   # Żeński, przyjazny
    "Elli": "MF3mGyEYCl7XYWbV9V6O",      # Żeński, młody
    "Emily": "LcfcDJNUP1GQjkzn1xUU",     # Żeński, spokojny
    "Ethan": "g5CIjZEefAph4nQFvHAz",     # Męski, młody
    "Fin": "D38z5RcWu1voky8WS1ja",       # Męski, irlandzki
    "Freya": "jsCqWAovK2LkecY7zXl4",     # Żeński, amerykański
    "Gigi": "jBpfuIE2acCO8z3wKNLl",      # Żeński, animowany
    "Giovanni": "zcAOhNBS3c14rBihAFp1",  # Męski, włoski
    "Glinda": "z9fAnlkpzviPz146aGWa",    # Żeński, czarodziejski
    "Grace": "oWAxZDx7w5VEj9dCyTzz",     # Żeński, południowy
    "Harry": "SOYHLrjzK2X1ezoPC6cr",     # Męski, młody
    "James": "ZQe5CZNOzWyzPSCn5a3c",     # Męski, australijski
    "Jeremy": "bVMeCyTHy58xNoL34h3p",    # Męski, irlandzki-amerykański
    "Jessie": "t0jbNlBVZ17f02VDIeMI",    # Męski, amerykański
    "Joseph": "Zlb1dXrM653N07WRdFW3",    # Męski, brytyjski
    "Josh": "TxGEqnHWrfWFTfGW9XjX",      # Męski, młody
    "Liam": "TX3LPaxmHKxFdv7VOQHJ",      # Męski, neutralny
    "Matilda": "XrExE9yKIg1WjnnlVkGX",   # Żeński, ciepły
    "Matthew": "Yko7PKHZNXotIFUBG7I9",   # Męski, narratorski
    "Michael": "flq6f7yk4E4fJM5XTYuZ",   # Męski, starszy
    "Mimi": "zrHiDhphv9ZnVXBqCLjz",      # Żeński, animowany
    "Nicole": "piTKgcLEGmPE4e6mEKli",    # Żeński, szepczący
    "Patrick": "ODq5zmih8GrVes37Dizd",   # Męski, młody
    "Rachel": "21m00Tcm4TlvDq8ikWAM",    # Żeński, spokojny
    "Sam": "yoZ06aMxZJJ28mfd3POQ",       # Męski, dynamiczny
    "Serena": "pMsXgVXv3BLzUgSXRplE",    # Żeński, spokojny (dobry dla narracji)
    "Thomas": "GBv7mTt0atIp3Br8iCZE",    # Męski, spokojny
}


class ElevenLabsAudioGenerator:
    """Generator audio z ElevenLabs API"""

    def __init__(self, api_key: str, voice_id: str = None, model: str = "eleven_multilingual_v2"):
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id or RECOMMENDED_VOICES["Adam"]
        self.model = model
        self.generated_count = 0
        self.total_chars = 0

    def generate_audio(self, text: str, output_path: str) -> bool:
        """Generuje plik audio z tekstu"""
        try:
            audio = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                text=text,
                model_id=self.model,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True
                )
            )

            # Zapisz audio do pliku
            with open(output_path, 'wb') as f:
                for chunk in audio:
                    f.write(chunk)

            self.generated_count += 1
            self.total_chars += len(text)
            return True

        except Exception as e:
            print(f"  Błąd generowania: {e}")
            return False

    def get_available_voices(self) -> List[Dict]:
        """Pobiera listę dostępnych głosów"""
        try:
            response = self.client.voices.get_all()
            return [{"name": v.name, "id": v.voice_id} for v in response.voices]
        except Exception as e:
            print(f"Błąd pobierania głosów: {e}")
            return []


def filter_texts_by_source(texts: List[Dict], sources: List[str] = None) -> List[Dict]:
    """Filtruje teksty po źródle (np. tylko ab.h3c)"""
    if not sources:
        return texts

    filtered = []
    for t in texts:
        source = t.get('source', '')
        for s in sources:
            if s in source:
                filtered.append(t)
                break
    return filtered


def remove_duplicates(texts: List[Dict]) -> List[Dict]:
    """Usuwa duplikaty tekstów"""
    seen = set()
    unique = []
    for t in texts:
        text = t['text'].strip()
        if text not in seen:
            seen.add(text)
            unique.append(t)
    return unique


def process_campaign(
    input_file: str,
    output_dir: str,
    api_key: str,
    voice_id: str = None,
    sources: List[str] = None,
    limit: int = None,
    dry_run: bool = False
):
    """Przetwarza kampanię i generuje pliki audio"""

    # Wczytaj teksty
    print(f"Wczytywanie: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        texts = json.load(f)

    print(f"  Załadowano {len(texts)} tekstów")

    # Filtruj po źródle
    if sources:
        texts = filter_texts_by_source(texts, sources)
        print(f"  Po filtrowaniu źródeł: {len(texts)} tekstów")

    # Usuń duplikaty
    texts = remove_duplicates(texts)
    print(f"  Po usunięciu duplikatów: {len(texts)} tekstów")

    # Ogranicz liczbę
    if limit:
        texts = texts[:limit]
        print(f"  Ograniczono do: {len(texts)} tekstów")

    # Policz znaki
    total_chars = sum(len(t['text']) for t in texts)
    print(f"  Łącznie znaków: {total_chars:,}")

    if dry_run:
        print("\n[DRY RUN] Nie generuję audio, tylko podgląd.")
        print(f"\nSzacowany koszt (Creator $22/mo, 100k znaków):")
        print(f"  {total_chars:,} znaków = {total_chars/100000:.1%} miesięcznego limitu")
        return

    # Utwórz katalog wyjściowy
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Inicjalizuj generator
    print(f"\nInicjalizacja ElevenLabs...")
    generator = ElevenLabsAudioGenerator(api_key, voice_id)

    # Generuj audio
    print(f"\nGenerowanie audio do: {output_dir}")
    print("="*60)

    for i, text_entry in enumerate(texts):
        text = text_entry['text']
        text_id = text_entry.get('id', i)
        source = text_entry.get('source', 'unknown').replace(':', '_').replace('.h3c', '')

        # Nazwa pliku
        filename = f"{source}_{text_id:04d}.mp3"
        filepath = output_path / filename

        # Pomiń jeśli już istnieje
        if filepath.exists():
            print(f"  [{i+1}/{len(texts)}] Pomijam (istnieje): {filename}")
            continue

        print(f"  [{i+1}/{len(texts)}] Generuję: {filename} ({len(text)} znaków)")

        success = generator.generate_audio(text, str(filepath))

        if not success:
            print(f"    BŁĄD - pomijam")

        # Małe opóźnienie aby nie przekroczyć limitu API
        time.sleep(0.5)

    print("="*60)
    print(f"\nZakończono!")
    print(f"  Wygenerowano: {generator.generated_count} plików")
    print(f"  Zużyto znaków: {generator.total_chars:,}")


def list_voices(api_key: str):
    """Wyświetla listę dostępnych głosów"""
    print("Pobieranie listy głosów z ElevenLabs...")
    generator = ElevenLabsAudioGenerator(api_key)
    voices = generator.get_available_voices()

    print(f"\nDostępne głosy ({len(voices)}):")
    print("="*60)
    for v in voices:
        print(f"  {v['name']}: {v['id']}")

    print("\nRekomendowane głosy dla narracji polskiej:")
    print("  Adam (męski, głęboki): pNInz6obpgDQGcFmaJgB")
    print("  Antoni (męski, przyjazny): ErXwobaYiN019PkySvjV")
    print("  Rachel (żeński, spokojny): 21m00Tcm4TlvDq8ikWAM")


def main():
    parser = argparse.ArgumentParser(
        description='Generator audio z tekstów Heroes 3 (ElevenLabs)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  # Lista głosów
  python generate_audio_elevenlabs.py --list-voices --api-key YOUR_KEY

  # Podgląd (bez generowania)
  python generate_audio_elevenlabs.py texts.json --api-key KEY --dry-run

  # Generowanie z domyślnym głosem
  python generate_audio_elevenlabs.py texts.json --api-key KEY -o audio/

  # Tylko wybrane źródło (np. ab.h3c)
  python generate_audio_elevenlabs.py texts.json --api-key KEY --source ab.h3c

  # Limit tekstów
  python generate_audio_elevenlabs.py texts.json --api-key KEY --limit 10
        """
    )

    parser.add_argument('input', nargs='?', help='Plik JSON z tekstami')
    parser.add_argument('--api-key', required=True, help='Klucz API ElevenLabs')
    parser.add_argument('--voice', default=None, help='ID głosu (domyślnie: Adam)')
    parser.add_argument('--output', '-o', default='audio_output', help='Katalog wyjściowy')
    parser.add_argument('--source', action='append', help='Filtruj po źródle (np. ab.h3c)')
    parser.add_argument('--limit', type=int, help='Ogranicz liczbę tekstów')
    parser.add_argument('--dry-run', action='store_true', help='Tylko podgląd, bez generowania')
    parser.add_argument('--list-voices', action='store_true', help='Wyświetl dostępne głosy')

    args = parser.parse_args()

    if args.list_voices:
        list_voices(args.api_key)
        return

    if not args.input:
        parser.error("Podaj plik JSON z tekstami lub użyj --list-voices")

    process_campaign(
        input_file=args.input,
        output_dir=args.output,
        api_key=args.api_key,
        voice_id=args.voice,
        sources=args.source,
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
