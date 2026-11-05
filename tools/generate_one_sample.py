#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje audio dla JEDNEGO wybranego tekstu z dowolnej kampanii - pilotaz przed
pelnym przebiegiem generate_campaign_audio.py na calej kampanii.

Uzywa dokladnie tej samej logiki parsowania/mapowania glosow co
generate_campaign_audio.py (ktory poprawnie wygenerowal kampanie Pod), zeby
probka wiernie pokazywala jak zabrzmi docelowe audio.

Uzycie:
    py -3 generate_one_sample.py <kod_kampanii> <id>
    py -3 generate_one_sample.py Drz 43

Zapisuje do audio_<kod>_campaign/<kod>_<id>.mp3 (dokladnie tam, gdzie trafi przy
pelnym przebiegu) - jesli plik juz istnieje, NIE nadpisuje bez --force.

Wymaga zmiennej srodowiskowej ELEVENLABS_API_KEY.
"""

import os
import re
import sys
import json
import argparse

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CHRONICLES_DIR = os.path.join(TOOLS_DIR, "chronicles_voiceover")

VOICES = {
    'narrator': '0el4HQ5fH8KITMM7DKzD',
    'T': 'o2xdfKUpc1Bwq7RchZuW',
    'tarnum': 'o2xdfKUpc1Bwq7RchZuW',
    'npc_m': 'XoHJ8hwSLOtb2sXYdAzv',
    'npc_f': 'N0GCuK2B0qwWozQNTS8F',
}


def clean_text(text: str) -> str:
    text = text.replace('\\n', ' ').replace('\n', ' ')
    return re.sub(r' +', ' ', text).strip()


def has_speakable_content(text: str) -> bool:
    return bool(re.search(r'\w', text, re.UNICODE))


def parse_text_with_quotes(text: str, voices: list) -> list:
    segments = []
    quote_index = 0
    last_end = 0
    pattern = r'"([^"]+)"'
    for match in re.finditer(pattern, text):
        start, end = match.start(), match.end()
        quote_text = match.group(1)
        if start > last_end:
            narrator_text = clean_text(text[last_end:start])
            if narrator_text and has_speakable_content(narrator_text):
                segments.append({'voice': 'narrator', 'text': narrator_text})
        voice = voices[quote_index] if quote_index < len(voices) else 'npc_m'
        cleaned_quote = clean_text(quote_text)
        if has_speakable_content(cleaned_quote):
            segments.append({'voice': voice, 'text': cleaned_quote})
        quote_index += 1
        last_end = end
    if last_end < len(text):
        remaining = clean_text(text[last_end:])
        if remaining and has_speakable_content(remaining):
            segments.append({'voice': 'narrator', 'text': remaining})
    if not segments:
        segments.append({'voice': 'narrator', 'text': clean_text(text)})
    return segments


def find_entry(campaign_code, text_id):
    edit_file = os.path.join(CHRONICLES_DIR, "audio_prepared", f"{campaign_code}_bmp_campaign_texts_ab_edit.txt")
    if not os.path.exists(edit_file):
        raise FileNotFoundError(f"Brak pliku: {edit_file}")
    with open(edit_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^(\d+)\|(\[.*?\])\|(.+)$', line)
            if not m:
                continue
            if int(m.group(1)) != text_id:
                continue
            try:
                voices = json.loads(m.group(2))
            except json.JSONDecodeError:
                voices = []
            return {'id': text_id, 'voices': voices, 'text': m.group(3)}
    raise ValueError(f"Nie znaleziono ID {text_id} w {edit_file}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('campaign', help='Kod kampanii, np. Drz, Bun, Mie, Ogn, Sza, Wla')
    parser.add_argument('id', type=int, help='ID tekstu z pliku audio_prepared/<Kod>_bmp_campaign_texts_ab_edit.txt')
    parser.add_argument('--force', action='store_true', help='Nadpisz, jesli plik wyjsciowy juz istnieje')
    args = parser.parse_args()

    code_lower = args.campaign.lower()
    output_dir = os.path.join(CHRONICLES_DIR, f"audio_{code_lower}_campaign")
    output_path = os.path.join(output_dir, f"{code_lower}_{args.id:03d}.mp3")

    if os.path.exists(output_path) and not args.force:
        print(f"Plik juz istnieje: {output_path} (uzyj --force zeby nadpisac)")
        sys.exit(1)

    item = find_entry(args.campaign, args.id)
    segments = parse_text_with_quotes(item['text'], item['voices'])
    total_chars = sum(len(s['text']) for s in segments)

    print(f"=== {args.campaign} ID {item['id']} ({total_chars} znakow, {len(segments)} segmentow) ===")
    for i, seg in enumerate(segments):
        print(f"  {i+1}. [{seg['voice']:8}] {seg['text'][:70]}{'...' if len(seg['text']) > 70 else ''}")

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("\nUstaw zmienna srodowiskowa ELEVENLABS_API_KEY zeby faktycznie wygenerowac audio.")
        print("(powyzej widac tylko podzial na segmenty/glosy - bez API)")
        sys.exit(1)

    from elevenlabs import ElevenLabs
    from elevenlabs.types import DialogueInput

    client = ElevenLabs(api_key=api_key)
    dialogue_inputs = [
        DialogueInput(text=seg['text'], voice_id=VOICES.get(seg['voice'], VOICES['narrator']))
        for seg in segments
    ]

    print("\nGenerowanie przez ElevenLabs...")
    audio_generator = client.text_to_dialogue.convert(
        inputs=dialogue_inputs,
        output_format="mp3_44100_128",
        model_id="eleven_v3",
        language_code="pl",
    )
    audio_data = b"".join(audio_generator)
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'wb') as f:
        f.write(audio_data)

    print(f"Zapisano: {output_path} ({len(audio_data) / 1024:.1f} KB)")


if __name__ == '__main__':
    main()
