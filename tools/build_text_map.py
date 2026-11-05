#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buduje text_map.txt (format wdrożeniowy, bez kolumny filtra mapy) dla dowolnej
kampanii Heroes Chronicles wprost z pliku audio_prepared/<kod>_bmp_campaign_texts_ab_edit.txt.

Warstwa filtra mapy (H3M_BOUNDARIES, generate_text_map_with_filter.py) jest tu
świadomie pominięta - wymagałaby ręcznego skanowania offsetów binarnych osobno dla
każdej kampanii. Bez niej dopasowanie działa w całej kampanii naraz (MapFilterMatches
zwraca true gdy filtr jest pusty) - w pełni funkcjonalne, tylko odrobinę mniej
precyzyjne w rzadkim przypadku identycznego tekstu na dwóch różnych mapach w obrębie
tej samej kampanii.

Format wyjściowy (identyczny jak deployowany text_map_with_filter.txt dla Woj, minus
ostatnia kolumna):
    {kod}_XXX|prefix_tekstu_40_znakow

Użycie:
    py -3 build_text_map.py <kod_kampanii>
    py -3 build_text_map.py --all
"""

import sys
import re
import os
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PREPARED_DIR = TOOLS_DIR / "chronicles_voiceover" / "audio_prepared"
OUTPUT_ROOT = TOOLS_DIR / "chronicles_voiceover"

CAMPAIGNS = ["Bun", "Drz", "Mie", "Ogn", "Pod", "Sza", "Wla", "Woj"]
PREFIX_LEN = 40

LINE_RE = re.compile(r'^(\d+)\|(\[.*?\])\|(.*)$')


def build_for_campaign(code: str) -> str:
    edit_path = PREPARED_DIR / f"{code}_bmp_campaign_texts_ab_edit.txt"
    if not edit_path.exists():
        raise FileNotFoundError(f"Brak pliku: {edit_path}")

    out_dir = OUTPUT_ROOT / f"audio_{code.lower()}_campaign"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "text_map.txt"

    entries = 0
    skipped = 0
    with open(edit_path, encoding='utf-8') as f, open(out_path, 'w', encoding='utf-8') as out:
        out.write("# text_map.txt (bez filtra mapy)\n")
        out.write(f"# Format: {code.lower()}_XXX|prefix_tekstu  (dopasowuje w calej kampanii)\n")
        out.write(f"# Wygenerowane przez build_text_map.py z {edit_path.name}\n\n")

        for line in f:
            line = line.rstrip('\n')
            if not line.strip() or line.startswith('#'):
                if line.startswith('# SKIP'):
                    skipped += 1
                continue
            m = LINE_RE.match(line)
            if not m:
                continue
            tid = int(m.group(1))
            text = m.group(3)
            prefix = text[:PREFIX_LEN]
            out.write(f"{code.lower()}_{tid:03d}|{prefix}\n")
            entries += 1

    print(f"{code}: {entries} wpisow ({skipped} SKIP pominietych) -> {out_path}")
    return str(out_path)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--all':
        for code in CAMPAIGNS:
            try:
                build_for_campaign(code)
            except FileNotFoundError as e:
                print(f"POMINIETO {code}: {e}")
    else:
        code = sys.argv[1]
        if code not in CAMPAIGNS:
            print(f"Nieznany kod kampanii: {code}. Oczekiwano jednego z: {CAMPAIGNS}")
            sys.exit(1)
        build_for_campaign(code)


if __name__ == '__main__':
    main()
