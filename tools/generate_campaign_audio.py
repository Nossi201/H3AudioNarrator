#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje audio dla dowolnej kampanii Heroes Chronicles z pliku audio_prepared/*_edit.txt,
uzywajac docelowych glosow Voice Library (nie premade). Wzorowane na generate_woj_campaign.py,
ale sparametryzowane po kodzie kampanii i z ORYGINALNYM (nie zamienionym) mapowaniem glosow
zgodnym z generate_dialogue.py - zamiana T<->npc_m w generate_woj_campaign.py byla
jednorazowa, specyficzna dla juz wygenerowanej kampanii Woj.

Uzycie:
    py -3 generate_campaign_audio.py <kod_kampanii>
    (np. py -3 generate_campaign_audio.py Pod)

Wymaga zmiennej srodowiskowej ELEVENLABS_API_KEY.
"""

import os
import re
import sys
import json
import time
from elevenlabs import ElevenLabs
from elevenlabs.types import DialogueInput

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    raise RuntimeError("Ustaw zmienna srodowiskowa ELEVENLABS_API_KEY")

VOICES = {
    'narrator': '0el4HQ5fH8KITMM7DKzD',
    'T': 'o2xdfKUpc1Bwq7RchZuW',
    'tarnum': 'o2xdfKUpc1Bwq7RchZuW',
    'npc_m': 'XoHJ8hwSLOtb2sXYdAzv',
    'npc_f': 'N0GCuK2B0qwWozQNTS8F',
}

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CHRONICLES_DIR = os.path.join(TOOLS_DIR, "chronicles_voiceover")


def parse_edit_file(filepath):
    texts = []
    skipped = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('# SKIP'):
                skipped += 1
                continue
            if line.startswith('#'):
                continue
            match = re.match(r'^(\d+)\|(\[.*?\])\|(.+)$', line)
            if match:
                text_id = int(match.group(1))
                voices_str = match.group(2)
                text = match.group(3)
                try:
                    voices = json.loads(voices_str)
                except json.JSONDecodeError:
                    voices = []
                texts.append({'id': text_id, 'voices': voices, 'text': text})
    print(f"Pominieto {skipped} tekstow oznaczonych SKIP")
    return texts


def clean_text(text: str) -> str:
    text = text.replace('\\n', ' ')
    text = text.replace('\n', ' ')
    text = re.sub(r' +', ' ', text)
    return text.strip()


def has_speakable_content(text: str) -> bool:
    """ElevenLabs odrzuca segmenty bez zadnego znaku alfanumerycznego (np. sam '...')."""
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
            narrator_text = text[last_end:start].strip()
            cleaned = clean_text(narrator_text)
            if narrator_text and has_speakable_content(cleaned):
                segments.append({'voice': 'narrator', 'text': cleaned})
        voice = voices[quote_index] if quote_index < len(voices) else 'npc_m'
        cleaned_quote = clean_text(quote_text)
        if has_speakable_content(cleaned_quote):
            segments.append({'voice': voice, 'text': cleaned_quote})
        quote_index += 1
        last_end = end
    if last_end < len(text):
        remaining = text[last_end:].strip()
        cleaned = clean_text(remaining)
        if remaining and has_speakable_content(cleaned):
            segments.append({'voice': 'narrator', 'text': cleaned})
    if not segments:
        segments.append({'voice': 'narrator', 'text': clean_text(text)})
    return segments


def generate_audio(campaign_lower, text_id, voices, text, output_dir, client):
    segments = parse_text_with_quotes(text, voices)
    total_chars = sum(len(seg['text']) for seg in segments)

    print(f"\n[{text_id}] {len(segments)} segmentow, {total_chars} znakow")
    for i, seg in enumerate(segments):
        preview = seg['text'][:40]
        print(f"  {i+1}. [{seg['voice']:8}] {preview}...")

    dialogue_inputs = []
    for seg in segments:
        voice_id = VOICES.get(seg['voice'], VOICES['narrator'])
        dialogue_inputs.append(DialogueInput(text=seg['text'], voice_id=voice_id))

    print("  Generowanie...")
    audio_generator = client.text_to_dialogue.convert(
        inputs=dialogue_inputs,
        output_format="mp3_44100_128",
        model_id="eleven_v3",
        language_code="pl",
    )
    audio_data = b"".join(audio_generator)
    output_path = os.path.join(output_dir, f"{campaign_lower}_{text_id:03d}.mp3")
    with open(output_path, 'wb') as f:
        f.write(audio_data)

    size_kb = len(audio_data) / 1024
    print(f"  Zapisano: {output_path} ({size_kb:.1f} KB)")
    return {'id': text_id, 'voices': voices, 'segments': segments,
            'total_chars': total_chars, 'output_file': output_path, 'size_kb': size_kb}


def main():
    if len(sys.argv) < 2:
        print("Uzycie: py -3 generate_campaign_audio.py <kod_kampanii>")
        sys.exit(1)
    code = sys.argv[1]
    code_lower = code.lower()

    input_file = os.path.join(CHRONICLES_DIR, "audio_prepared", f"{code}_bmp_campaign_texts_ab_edit.txt")
    output_dir = os.path.join(CHRONICLES_DIR, f"audio_{code_lower}_campaign")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print(f"Generator audio dla kampanii {code}_bmp")
    print("=" * 60)

    texts = parse_edit_file(input_file)
    print(f"\nWczytano {len(texts)} tekstow do wygenerowania")
    total_chars = sum(len(t['text']) for t in texts)
    print(f"Lacznie znakow: {total_chars}")
    print(f"Szacowany czas: ~{len(texts) * 5} sekund")

    client = ElevenLabs(api_key=API_KEY)

    results = []
    errors = []
    skipped_existing = 0

    for i, item in enumerate(texts):
        output_path = os.path.join(output_dir, f"{code_lower}_{item['id']:03d}.mp3")
        if os.path.exists(output_path):
            print(f"\n[{i+1}/{len(texts)}] ID {item['id']} - juz istnieje, pomijam")
            skipped_existing += 1
            continue
        try:
            print(f"\n[{i+1}/{len(texts)}]", end="")
            result = generate_audio(code_lower, item['id'], item['voices'], item['text'], output_dir, client)
            results.append(result)
            time.sleep(0.5)
        except Exception as e:
            print(f"\n  BLAD dla ID {item['id']}: {e}")
            errors.append({'id': item['id'], 'error': str(e)})

    report = {
        'campaign': code, 'total_texts': len(texts), 'generated': len(results),
        'errors': len(errors), 'total_chars': total_chars,
        'results': results, 'error_list': errors,
    }
    report_path = os.path.join(output_dir, "generation_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("ZAKONCZONO")
    print(f"  Wygenerowano: {len(results)}/{len(texts)}")
    print(f"  Pominieto (juz istnialy): {skipped_existing}")
    print(f"  Bledy: {len(errors)}")
    print(f"  Raport: {report_path}")
    print("=" * 60)


if __name__ == '__main__':
    main()
