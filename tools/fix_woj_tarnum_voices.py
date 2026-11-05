#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naprawia 47 plikow kampanii Woj, w ktorych kwestie Tarnuma zostaly przez
pomylke nagrane glosem narratora (patrz analiza z 2026-09-13).

Przyczyna: generate_woj_campaign.py mial w slowniku VOICES klucz 'T', ale
plik audio_prepared/Woj_bmp_campaign_texts_ab_edit.txt (jak wszystkie
kampanie Chronicles) uzywa wylacznie tagu 'tarnum' - VOICES.get('tarnum', ...)
cicho spadal na glos narratora zamiast rzucic blad.

Ten skrypt:
- przetwarza WYLACZNIE 47 znanych, dotknietych ID (TARGET_IDS) - nie rusza
  pozostalych 190 poprawnych plikow, zeby nie marnowac kredytow API,
- domyslnie dziala w trybie DRY-RUN (tylko pokazuje segmenty i glosy,
  zero wywolan API, zero nadpisanych plikow) - wymaga --apply,
- przed nadpisaniem kazdego pliku robi kopie do audio_woj_campaign/
  _backup_before_tarnum_fix/ (pomija plik jesli kopia juz istnieje).

Uzycie:
    py -3 fix_woj_tarnum_voices.py                # podglad (bezpieczne, bez API)
    py -3 fix_woj_tarnum_voices.py --apply         # realne generowanie + nadpisanie
    py -3 fix_woj_tarnum_voices.py --apply --id 46 # tylko jeden ID (do testu)

Wymaga zmiennej ELEVENLABS_API_KEY tylko przy --apply.
"""

import os
import re
import sys
import json
import time
import argparse

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
CHRONICLES_DIR = os.path.join(TOOLS_DIR, "chronicles_voiceover")
INPUT_FILE = os.path.join(CHRONICLES_DIR, "audio_prepared", "Woj_bmp_campaign_texts_ab_edit.txt")
OUTPUT_DIR = os.path.join(CHRONICLES_DIR, "audio_woj_campaign")
BACKUP_DIR = os.path.join(OUTPUT_DIR, "_backup_before_tarnum_fix")

# Poprawiony slownik: 'tarnum' dostaje glos, ktory mial dostac zgodnie z
# zamierzona zamiana T<->npc_m (byl kluczem 'T' w oryginalnym, zepsutym
# skrypcie). npc_m i narrator bez zmian - te dzialaly poprawnie.
VOICES = {
    'narrator': '0el4HQ5fH8KITMM7DKzD',
    'tarnum': 'XoHJ8hwSLOtb2sXYdAzv',   # naprawione: bylo cicho 'narrator'
    'npc_m': 'o2xdfKUpc1Bwq7RchZuW',    # bez zmian (zamiana dzialala poprawnie)
    'npc_f': 'N0GCuK2B0qwWozQNTS8F',
}

# 47 ID ustalonych 2026-09-13 przez skan Woj_bmp_campaign_texts_ab_edit.txt
# pod katem tagu "tarnum" - to jedyne pliki dotkniete bugiem.
TARGET_IDS = [
    35, 41, 46, 47, 49, 51, 52, 72, 79, 112, 126, 141, 152, 153, 154, 157,
    159, 161, 198, 202, 220, 246, 247, 248, 249, 250, 255, 258, 259, 260,
    262, 263, 264, 265, 268, 272, 275, 281, 283, 285, 290, 296, 299, 313,
    328, 332, 338,
]


def parse_edit_file(filepath, wanted_ids):
    texts = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^(\d+)\|(\[.*?\])\|(.+)$', line)
            if not m:
                continue
            text_id = int(m.group(1))
            if text_id not in wanted_ids:
                continue
            try:
                voices = json.loads(m.group(2))
            except json.JSONDecodeError:
                voices = []
            texts.append({'id': text_id, 'voices': voices, 'text': m.group(3)})
    return texts


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


def print_preview(item):
    segments = parse_text_with_quotes(item['text'], item['voices'])
    print(f"\n[ID {item['id']}] -> {OUTPUT_DIR}\\woj_{item['id']:03d}.mp3")
    for i, seg in enumerate(segments):
        marker = "  <- NAPRAWIONE (bylo: narrator)" if seg['voice'] == 'tarnum' else ""
        preview = seg['text'][:70]
        print(f"  {i+1}. [{seg['voice']:8}] {preview}{'...' if len(seg['text']) > 70 else ''}{marker}")


def apply_one(item, client):
    import shutil
    from elevenlabs.types import DialogueInput

    output_path = os.path.join(OUTPUT_DIR, f"woj_{item['id']:03d}.mp3")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"woj_{item['id']:03d}.mp3")
    if os.path.exists(output_path) and not os.path.exists(backup_path):
        shutil.copy2(output_path, backup_path)
        print(f"  Kopia zapasowa -> {backup_path}")

    segments = parse_text_with_quotes(item['text'], item['voices'])
    dialogue_inputs = [
        DialogueInput(text=seg['text'], voice_id=VOICES.get(seg['voice'], VOICES['narrator']))
        for seg in segments
    ]

    audio_generator = client.text_to_dialogue.convert(
        inputs=dialogue_inputs,
        output_format="mp3_44100_128",
        model_id="eleven_v3",
        language_code="pl",
    )
    audio_data = b"".join(audio_generator)
    with open(output_path, 'wb') as f:
        f.write(audio_data)
    print(f"  Zapisano: {output_path} ({len(audio_data) / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--apply', action='store_true', help='Realnie generuj audio przez ElevenLabs i nadpisz pliki (domyslnie: tylko podglad)')
    parser.add_argument('--id', type=int, action='append', dest='only_ids', help='Ogranicz do pojedynczego ID (mozna podac kilka razy)')
    args = parser.parse_args()

    wanted_ids = set(args.only_ids) if args.only_ids else set(TARGET_IDS)
    unknown = wanted_ids - set(TARGET_IDS)
    if unknown:
        print(f"UWAGA: ID spoza znanej listy 47 dotknietych plikow: {sorted(unknown)} - pomijam.")
        wanted_ids -= unknown

    items = parse_edit_file(INPUT_FILE, wanted_ids)
    missing = wanted_ids - {it['id'] for it in items}
    if missing:
        print(f"UWAGA: nie znaleziono w pliku edit ID: {sorted(missing)}")

    print(f"Do przetworzenia: {len(items)} plikow z {len(TARGET_IDS)} znanych dotknietych.")

    if not args.apply:
        print("\n=== TRYB PODGLADU (bez API, bez zmian na dysku) - uzyj --apply zeby faktycznie wygenerowac ===")
        for item in items:
            print_preview(item)
        print(f"\nPodglad zakonczony. {len(items)} plikow zostanie nadpisanych po uruchomieniu z --apply.")
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("Ustaw zmienna srodowiskowa ELEVENLABS_API_KEY")
    from elevenlabs import ElevenLabs
    client = ElevenLabs(api_key=api_key)

    for item in items:
        print_preview(item)
        try:
            apply_one(item, client)
            time.sleep(0.5)
        except Exception as e:
            print(f"  BLAD dla ID {item['id']}: {e}")

    print("\nZAKONCZONO.")


if __name__ == '__main__':
    main()
