#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje audio dla tekstów mieszanych używając ElevenLabs text_to_dialogue API.
Ta funkcja automatycznie łączy segmenty z różnymi głosami w jeden plik audio.
"""

import os
import re
import json
from elevenlabs import ElevenLabs
from elevenlabs.types import DialogueInput

# API Key (ustaw zmienna srodowiskowa przed uruchomieniem skryptu)
API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    raise RuntimeError("Ustaw zmienna srodowiskowa ELEVENLABS_API_KEY")

# Głosy
VOICES = {
    'narrator': '0el4HQ5fH8KITMM7DKzD',
    'T': 'o2xdfKUpc1Bwq7RchZuW',        # Tarnum
    'tarnum': 'o2xdfKUpc1Bwq7RchZuW',
    'npc_m': 'XoHJ8hwSLOtb2sXYdAzv',
    'npc_f': 'N0GCuK2B0qwWozQNTS8F',
}


def parse_text_with_quotes(text: str, voices: list) -> list:
    """
    Dzieli tekst na segmenty: narracja i cytaty.
    """
    text = text.replace('\\n', '\n')

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

    # Tekst po ostatnim cytacie
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            segments.append({
                'voice': 'narrator',
                'text': clean_text(remaining)
            })

    return segments


def clean_text(text: str) -> str:
    """Czyści tekst dla TTS"""
    text = text.replace('\n', ' ')
    text = re.sub(r' +', ' ', text)
    return text.strip()


def generate_dialogue(text_id: int, voices: list, text: str, output_dir: str = "audio_final", seed: int = None):
    """
    Generuje audio dla tekstu z dialogami używając text_to_dialogue API.

    Args:
        seed: Opcjonalny seed dla powtarzalnych wyników (ten sam seed = to samo audio)
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Generowanie dialogu dla tekstu #{text_id}")
    print(f"Głosy dla cytatów: {voices}")
    if seed is not None:
        print(f"Seed: {seed}")
    print(f"{'='*60}")

    # Parsuj tekst na segmenty
    segments = parse_text_with_quotes(text, voices)

    print(f"\nZnaleziono {len(segments)} segmentów:")
    total_chars = 0
    for i, seg in enumerate(segments):
        preview = seg['text'][:50]
        print(f"  {i+1}. [{seg['voice']:8}] {preview}...")
        total_chars += len(seg['text'])

    print(f"\nŁącznie znaków: {total_chars}")

    # Przygotuj DialogueInputs
    dialogue_inputs = []
    for seg in segments:
        voice_id = VOICES.get(seg['voice'], VOICES['narrator'])
        dialogue_inputs.append(DialogueInput(
            text=seg['text'],
            voice_id=voice_id
        ))

    # Generuj audio
    print("\nGenerowanie audio przez text_to_dialogue API...")
    client = ElevenLabs(api_key=API_KEY)

    # Przygotuj parametry
    params = {
        "inputs": dialogue_inputs,
        "output_format": "mp3_44100_128",
        "model_id": "eleven_v3",
        "language_code": "pl",  # wymusza polska fonetyke - bez tego model zgaduje
                                 # jezyk z tresci i gubi wymowe polskich znakow specjalnych
    }
    if seed is not None:
        params["seed"] = seed

    audio_generator = client.text_to_dialogue.convert(**params)

    # Zapisz audio
    audio_data = b"".join(audio_generator)
    output_path = os.path.join(output_dir, f"dialogue_{text_id}.mp3")

    with open(output_path, 'wb') as f:
        f.write(audio_data)

    print(f"\nZapisano: {output_path}")
    print(f"  Rozmiar: {len(audio_data) / 1024:.1f} KB")

    # Zapisz metadane
    metadata = {
        'id': text_id,
        'voices': voices,
        'segments': segments,
        'total_chars': total_chars,
        'output_file': output_path,
        'seed': seed
    }

    meta_path = os.path.join(output_dir, f"dialogue_{text_id}_meta.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return output_path


if __name__ == '__main__':
    # Test krótki - pojedyncze zdania
    text_test = """Sprowadzono przed twoje oblicze jakiegoś nieszczęśnika.

"Kim jesteś?" pytasz.

"Jestem bardem, królu."

"Nie jestem królem." odpowiadasz."""

    voices_test = ["T", "npc_m", "T"]

    # Test z seed dla powtarzalności
    SEED = 12345

    generate_dialogue(99, voices_test, text_test, "audio_final", seed=SEED)
