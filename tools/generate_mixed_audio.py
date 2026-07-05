#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje audio dla tekstów mieszanych (narrator + dialogi).
Dzieli tekst na segmenty i generuje osobno dla każdego głosu,
następnie łączy w jeden plik używając ffmpeg.
"""

import os
import re
import json
import subprocess
from pathlib import Path
from elevenlabs import ElevenLabs, VoiceSettings

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

# Ustawienia głosu
VOICE_SETTINGS = VoiceSettings(
    stability=0.5,
    similarity_boost=0.75,
    style=0.0,
    use_speaker_boost=True
)


def parse_text_with_quotes(text: str, voices: list) -> list:
    """
    Dzieli tekst na segmenty: narracja i cytaty.

    Args:
        text: Pełny tekst z cytatami w ""
        voices: Lista głosów dla kolejnych cytatów ['T', 'npc_m', ...]

    Returns:
        Lista segmentów: [{'voice': 'narrator'/'T'/..., 'text': '...'}, ...]
    """
    # Zamień \n na prawdziwe nowe linie
    text = text.replace('\\n', '\n')

    segments = []
    quote_index = 0
    last_end = 0

    # Znajdź wszystkie cytaty
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
                    'text': narrator_text
                })

        # Sam cytat
        if quote_index < len(voices):
            voice = voices[quote_index]
        else:
            voice = 'npc_m'  # domyślnie

        segments.append({
            'voice': voice,
            'text': quote_text
        })

        quote_index += 1
        last_end = end

    # Tekst po ostatnim cytacie
    if last_end < len(text):
        remaining = text[last_end:].strip()
        if remaining:
            segments.append({
                'voice': 'narrator',
                'text': remaining
            })

    return segments


def clean_text_for_tts(text: str) -> str:
    """Czyści tekst dla TTS"""
    text = text.replace('\n', ' ')
    text = re.sub(r' +', ' ', text)
    return text.strip()


def generate_segment_audio(client, segment: dict, output_dir: str, index: int) -> str:
    """
    Generuje audio dla jednego segmentu.
    Zwraca ścieżkę do pliku.
    """
    voice_id = VOICES.get(segment['voice'], VOICES['narrator'])
    text = clean_text_for_tts(segment['text'])

    if not text:
        return None

    print(f"  [{index}] {segment['voice']}: {text[:50]}...")

    # Generuj audio
    audio_generator = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VOICE_SETTINGS
    )

    # Zbierz dane audio
    audio_data = b"".join(audio_generator)

    # Zapisz segment
    segment_path = os.path.join(output_dir, f"segment_{index:02d}_{segment['voice']}.mp3")
    with open(segment_path, 'wb') as f:
        f.write(audio_data)

    return segment_path


def combine_audio_with_ffmpeg(segment_files: list, output_path: str, pause_ms: int = 400):
    """
    Łączy segmenty audio używając ffmpeg.
    """
    # Utwórz plik listy dla ffmpeg
    list_file = output_path.replace('.mp3', '_list.txt')

    with open(list_file, 'w', encoding='utf-8') as f:
        for i, file_path in enumerate(segment_files):
            if file_path and os.path.exists(file_path):
                # Użyj ścieżki bezwzględnej z ukośnikami w stylu Unix
                abs_path = os.path.abspath(file_path).replace('\\', '/')
                f.write(f"file '{abs_path}'\n")

    # Połącz używając ffmpeg
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_file,
        '-c', 'copy',
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"\nPołączono w: {output_path}")
            # Usuń plik listy
            os.remove(list_file)
            return True
        else:
            print(f"Błąd ffmpeg: {result.stderr}")
            return False
    except FileNotFoundError:
        print("ffmpeg nie znaleziony - segmenty są w folderze segments_X")
        print("Możesz połączyć je ręcznie lub zainstalować ffmpeg")
        return False


def generate_mixed_audio(text_id: int, voices: list, text: str, output_dir: str = "audio_final"):
    """
    Główna funkcja generująca audio dla tekstu mieszanego.
    """
    os.makedirs(output_dir, exist_ok=True)
    segments_dir = os.path.join(output_dir, f"segments_{text_id}")
    os.makedirs(segments_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Generowanie audio dla tekstu #{text_id}")
    print(f"Głosy: {voices}")
    print(f"{'='*60}")

    # Parsuj tekst na segmenty
    segments = parse_text_with_quotes(text, voices)

    print(f"\nZnaleziono {len(segments)} segmentów:")
    for i, seg in enumerate(segments):
        preview = seg['text'][:60].replace('\n', ' ')
        print(f"  {i+1}. [{seg['voice']}] {preview}...")

    # Inicjalizuj klienta
    client = ElevenLabs(api_key=API_KEY)

    # Generuj audio dla każdego segmentu
    print(f"\nGenerowanie segmentów...")
    segment_files = []
    total_chars = 0

    for i, segment in enumerate(segments):
        file_path = generate_segment_audio(client, segment, segments_dir, i)
        segment_files.append(file_path)
        total_chars += len(segment['text'])

    print(f"\nWygenerowano {len(segment_files)} segmentów ({total_chars} znaków)")

    # Połącz segmenty
    final_path = os.path.join(output_dir, f"text_{text_id}_final.mp3")
    combine_audio_with_ffmpeg(segment_files, final_path)

    # Zapisz metadane
    metadata = {
        'id': text_id,
        'voices': voices,
        'segments': segments,
        'total_chars': total_chars,
        'segment_files': segment_files,
        'output_file': final_path
    }

    meta_path = os.path.join(output_dir, f"text_{text_id}_meta.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Metadane: {meta_path}")

    return final_path


if __name__ == '__main__':
    # Test - tekst 46
    text_46 = """Sprowadzono przed twoje oblicze jakiegoś nieszczęśnika. Wygląda, jakby od dłuższego czasu ukrywał się w lesie i przymierał głodem, co można poznać bo jego wychudzonych żebrach. Żołnierz, który sprowadził tego oberwańca, mówi, że biedak podejrzanie kręcił się wokół obozu.

"Kim jesteś?" pytasz.

"Jestem bardem, królu."

"Nie jestem królem."

"Z tego co wiem jesteś. Mówi się tez że chronisz nas bardów przed prawem królów-magów w zamian za nasze opowieści."

"To prawda." odpowiadasz z trudem opanowując emocje. A więc stary bard, który umarł w twoich ramionach, nie był ostatnim. Historia twojego ludu nie jest jeszcze stracona!"""

    voices_46 = ["T", "npc_m", "T", "npc_m", "T"]

    generate_mixed_audio(46, voices_46, text_46, "audio_final")
