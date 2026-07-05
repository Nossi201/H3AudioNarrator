#pragma once

#include <string>

/**
 * @brief Reprezentuje pojedynczy zasob audio.
 *        Odpowiada encji "Audio" z diagramu.
 *
 * Pola:
 *   id_Audio   - unikalny kod kompozytowy "{kampania}_{lokalneId:03d}" np. "woj_032"
 *                (= nazwa pliku bez .mp3, = ID w text_map.txt). Zastapil goly int,
 *                zeby ID roznych kampanii nigdy sie nie zderzaly (kazda kampania
 *                liczy lokalne ID od 0 niezaleznie w narzedziach offline).
 *   directory  - pelna sciezka do pliku MP3
 *   unlocked   - czy audio jest odblokowane dla gracza
 *   mapFilter  - fragment nazwy mapy H3 na ktorej audio ma grac;
 *                pusty lub "*" = graj na wszystkich mapach.
 *                Odpowiada polu "campaign (Int)" z diagramu - zmienione
 *                na string po analizie H3API (bigCampaignIndex nie obsluguje
 *                kampanii niestandardowych; mapName jest pewniejsze).
 *   time       - dlugosc pliku w ms (0 = nieznana, wypelniana przy otwarciu)
 */
struct Audio
{
    std::string id_Audio;
    std::string directory;
    bool        unlocked;
    std::string mapFilter;
    int         time;

    Audio()
        : unlocked(true), time(0)
    {}

    Audio(const std::string& id, const std::string& dir, bool locked = false, const std::string& filter = "")
        : id_Audio(id), directory(dir), unlocked(!locked), mapFilter(filter), time(0)
    {}
};
