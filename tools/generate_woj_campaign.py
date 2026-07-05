#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje audio dla kampanii Woj_bmp z pliku _edit.txt
Zamienia głosy: T <-> npc_m (na życzenie użytkownika)
"""

import os
import re
import json
import time
from elevenlabs import ElevenLabs
from elevenlabs.types import DialogueInput

# API Key (ustaw zmienna srodowiskowa przed uruchomieniem skryptu)
API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    raise RuntimeError("Ustaw zmienna srodowiskowa ELEVENLABS_API_KEY")

# Głosy - ZAMIENIONE T z npc_m
VOICES = {
    'narrator': '0el4HQ5fH8KITMM7DKzD',
    'T': 'XoHJ8hwSLOtb2sXYdAzv',        # Było npc_m, teraz T
    'npc_m': 'o2xdfKUpc1Bwq7RchZuW',    # Było T, teraz npc_m
    'npc_f': 'N0GCuK2B0qwWozQNTS8F',
}

INPUT_FILE = r"audio_prepared\Woj_bmp_campaign_texts_ab_edit.txt"
OUTPUT_DIR = r"audio_woj_campaign"


def parse_edit_file(filepath):
    """
    Parsuje plik _edit.txt i zwraca listę tekstów do wygenerowania.
    Format: ID|[głosy]|TEKST
    Pomija linie zaczynające się od # SKIP
    """
    texts = []
    skipped = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Pomiń puste linie
            if not line:
                continue

            # Pomiń komentarze SKIP
            if line.startswith('# SKIP'):
                skipped += 1
                continue

            # Pomiń inne komentarze (np. # EDYTUJ:, nagłówek pliku)
            if line.startswith('#'):
                continue

            # Parsuj format: ID|[voices]|TEXT
            match = re.match(r'^(\d+)\|(\[.*?\])\|(.+)$', line)
            if match:
                text_id = int(match.group(1))
                voices_str = match.group(2)
                text = match.group(3)

                # Parsuj głosy
                try:
                    voices = json.loads(voices_str)
                except json.JSONDecodeError:
                    voices = []

                texts.append({
                    'id': text_id,
                    'voices': voices,
                    'text': text
                })

    print(f"Pominieto {skipped} tekstow oznaczonych SKIP")
    return texts


def clean_text(text: str) -> str:
    """Czyści tekst dla TTS"""
    text = text.replace('\\n', ' ')
    text = text.replace('\n', ' ')
    text = re.sub(r' +', ' ', text)
    return text.strip()


def parse_text_with_quotes(text: str, voices: list) -> list:
    """
    Dzieli tekst na segmenty: narracja i cytaty.
    """
    segments = []
    quote_index = 0
    last_end = 0

    pattern = r'"([^"]+)"'

    for match in re.finditer(pattern, text):
        start, end = match.start(), match.end()
        quote_text = match.group(1)

        # Tekst przed cytatem (narracja)
        if start > last_end:
            narrator_text = text[last_end:start].strip()
            if narrator_text:
                segments.append({
                    'voice': 'narrator',
                    'text': clean_text(narrator_text)
                })

        # Sam cytat
        voice = voices[quote_index] if quote_index < len(voices) else 'npc_m'
        segments.append({
            'voice': voice,
            'text': clean_text(quote_text)
        })

        quote_index += 1
        last_end = end

    # Tekst po ostatnim cytacie lub cały tekst jeśli brak cytatów
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            segments.append({
                'voice': 'narrator',
                'text': clean_text(remaining)
            })

    # Jeśli nie było cytatów, cały tekst jest narracją
    if not segments:
        segments.append({
            'voice': 'narrator',
            'text': clean_text(text)
        })

    return segments


def generate_audio(text_id: int, voices: list, text: str, output_dir: str, client: ElevenLabs):
    """
    Generuje audio dla pojedynczego tekstu.
    """
    # Parsuj tekst na segmenty
    segments = parse_text_with_quotes(text, voices)

    total_chars = sum(len(seg['text']) for seg in segments)

    print(f"\n[{text_id}] {len(segments)} segmentow, {total_chars} znakow")
    for i, seg in enumerate(segments):
        preview = seg['text'][:40]
        print(f"  {i+1}. [{seg['voice']:8}] {preview}...")

    # Przygotuj DialogueInputs
    dialogue_inputs = []
    for seg in segments:
        voice_id = VOICES.get(seg['voice'], VOICES['narrator'])
        dialogue_inputs.append(DialogueInput(
            text=seg['text'],
            voice_id=voice_id
        ))

    # Generuj audio
    print(f"  Generowanie...")

    audio_generator = client.text_to_dialogue.convert(
        inputs=dialogue_inputs,
        output_format="mp3_44100_128",
        model_id="eleven_v3"
    )

    # Zapisz audio
    audio_data = b"".join(audio_generator)
    output_path = os.path.join(output_dir, f"woj_{text_id:03d}.mp3")

    with open(output_path, 'wb') as f:
        f.write(audio_data)

    size_kb = len(audio_data) / 1024
    print(f"  Zapisano: {output_path} ({size_kb:.1f} KB)")

    return {
        'id': text_id,
        'voices': voices,
        'segments': segments,
        'total_chars': total_chars,
        'output_file': output_path,
        'size_kb': size_kb
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("Generator audio dla kampanii Woj_bmp")
    print("Glosy zamienione: T <-> npc_m")
    print("=" * 60)

    # Wczytaj teksty
    texts = parse_edit_file(INPUT_FILE)
    print(f"\nWczytano {len(texts)} tekstow do wygenerowania")

    # Statystyki
    total_chars = sum(len(t['text']) for t in texts)
    print(f"Lacznie znakow: {total_chars}")
    print(f"Szacowany czas: ~{len(texts) * 5} sekund")

    # Inicjalizuj klienta
    client = ElevenLabs(api_key=API_KEY)

    # Generuj audio
    results = []
    errors = []
    skipped_existing = 0

    for i, item in enumerate(texts):
        # Sprawdź czy plik już istnieje
        output_path = os.path.join(OUTPUT_DIR, f"woj_{item['id']:03d}.mp3")
        if os.path.exists(output_path):
            print(f"\n[{i+1}/{len(texts)}] ID {item['id']} - juz istnieje, pomijam")
            skipped_existing += 1
            continue

        try:
            print(f"\n[{i+1}/{len(texts)}]", end="")
            result = generate_audio(
                item['id'],
                item['voices'],
                item['text'],
                OUTPUT_DIR,
                client
            )
            results.append(result)

            # Mała pauza między requestami
            time.sleep(0.5)

        except Exception as e:
            print(f"\n  BLAD dla ID {item['id']}: {e}")
            errors.append({'id': item['id'], 'error': str(e)})

    # Zapisz raport
    report = {
        'total_texts': len(texts),
        'generated': len(results),
        'errors': len(errors),
        'total_chars': total_chars,
        'results': results,
        'error_list': errors
    }

    report_path = os.path.join(OUTPUT_DIR, "generation_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"ZAKONCZONO")
    print(f"  Wygenerowano: {len(results)}/{len(texts)}")
    print(f"  Pominieto (juz istnialy): {skipped_existing}")
    print(f"  Bledy: {len(errors)}")
    print(f"  Raport: {report_path}")
    print("=" * 60)


if __name__ == '__main__':
    main()
