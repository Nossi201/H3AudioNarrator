#pragma once

#include "Audio.hpp"
#include <vector>
#include <map>
#include <fstream>
#include <sstream>
#include <cstring>
#include <cctype>
#include <algorithm>

/**
 * @brief Ustawienia odtwarzacza.
 *
 * unlocked_per_map: per-mapowa lista odblokowanych kodow audio
 *   Klucz = znormalizowana (trim + ASCII-lowercase) nazwa mapy z H3API (game->mapInfo.mapName).
 *   Klucz "" = stary format / brak mapy - NIE scalany z nazwanymi mapami (niejednoznaczny bucket).
 *
 * Kod audio: string kompozytowy "{kampania}_{lokalneId:03d}" np. "woj_032" (= nazwa pliku bez .mp3).
 *
 * Format INI:
 *   volume=500
 *   auto_start=1
 *   unlocked_|nazwa mapy|=woj_001,woj_005,woj_023
 */
struct Settings
{
    int                volume;
    bool               auto_start;
    bool               linger_after_close;
    bool               playlist_mode;
    std::string        selected_audio;
    std::vector<Audio> audio_array;

    std::map<std::string, std::vector<std::string>> unlocked_per_map;

    Settings()
        : volume(500), auto_start(true), linger_after_close(true),
          playlist_mode(false), m_currentMap("")
    {}

    // -----------------------------------------------------------------------
    void SetCurrentMap(const char* mapName) { m_currentMap = NormalizeMapKey(mapName ? mapName : ""); }
    const std::string& GetCurrentMap() const { return m_currentMap; }

    std::vector<std::string>& GetCurrentUnlocked()
    {
        return unlocked_per_map[m_currentMap];
    }

    const std::vector<std::string>& GetCurrentUnlocked() const
    {
        static const std::vector<std::string> empty;
        auto it = unlocked_per_map.find(m_currentMap);
        return (it != unlocked_per_map.end()) ? it->second : empty;
    }

    // -----------------------------------------------------------------------
    void Save(const char* path) const
    {
        std::ofstream f(path, std::ios::out | std::ios::trunc);
        if (!f.is_open())
            return;

        f << "volume="              << volume                        << "\n";
        f << "auto_start="          << (auto_start ? 1 : 0)         << "\n";
        f << "linger_after_close="  << (linger_after_close ? 1 : 0) << "\n";
        f << "playlist_mode="       << (playlist_mode ? 1 : 0)      << "\n";
        f << "selected_audio="      << selected_audio                << "\n";

        for (const auto& kv : unlocked_per_map)
        {
            if (kv.second.empty()) continue;
            f << "unlocked_|" << kv.first << "|=";
            for (size_t i = 0; i < kv.second.size(); i++)
            {
                if (i > 0) f << ",";
                f << kv.second[i];
            }
            f << "\n";
        }
    }

    // -----------------------------------------------------------------------
    bool Load(const char* path)
    {
        std::ifstream f(path);
        if (!f.is_open())
            return false;

        char line[4096];
        while (f.getline(line, sizeof(line)))
        {
            char* eq = strchr(line, '=');
            if (!eq) continue;
            *eq = '\0';
            const char* key = line;
            const char* val = eq + 1;

            if      (strcmp(key, "volume")             == 0) volume             = atoi(val);
            else if (strcmp(key, "auto_start")         == 0) auto_start         = (atoi(val) != 0);
            else if (strcmp(key, "linger_after_close") == 0) linger_after_close = (atoi(val) != 0);
            else if (strcmp(key, "playlist_mode")      == 0) playlist_mode      = (atoi(val) != 0);
            else if (strcmp(key, "selected_audio")     == 0) selected_audio     = MigrateLegacyId(val);
            else if (strcmp(key, "unlocked")           == 0)
            {
                // Kompatybilnosc wsteczna: bardzo stary format → mapa "" (niejednoznaczna, nie scalac dalej)
                MergeUnlockedList(val, unlocked_per_map[""]);
            }
            else if (strncmp(key, "unlocked_|", 10) == 0)
            {
                // Format: unlocked_|NazwaMapy|
                const char* mapStart = key + 10;
                const char* mapEnd   = strrchr(mapStart, '|');
                if (!mapEnd) continue;
                std::string mapName = NormalizeMapKey(std::string(mapStart, mapEnd - mapStart));
                // Scalanie: rozne warianty wielkosci liter tej samej mapy normalizuja sie
                // do tego samego klucza, wiec kolejne wpisy doklejaja sie (z deduplikacja) do jednej listy.
                MergeUnlockedList(val, unlocked_per_map[mapName]);
            }
        }
        return true;
    }

    // -----------------------------------------------------------------------
    void ApplyUnlockState()
    {
        for (auto& a : audio_array)
            a.unlocked = false;

        for (const auto& kv : unlocked_per_map)
            for (const std::string& id : kv.second)
                if (Audio* a = FindAudio(id))
                    a->unlocked = true;
    }

    // -----------------------------------------------------------------------
    bool UnlockAudio(const std::string& id)
    {
        std::vector<std::string>& ids = GetCurrentUnlocked();

        for (const std::string& existing : ids)
            if (existing == id) return false;

        ids.push_back(id);

        if (Audio* a = FindAudio(id))
            a->unlocked = true;

        return true;
    }

    // -----------------------------------------------------------------------
    bool LockAudio(const std::string& id)
    {
        if (Audio* a = FindAudio(id))
            a->unlocked = false;

        bool found = false;
        for (auto& kv : unlocked_per_map)
        {
            auto it = std::find(kv.second.begin(), kv.second.end(), id);
            if (it != kv.second.end())
            {
                kv.second.erase(it);
                found = true;
            }
        }
        return found;
    }

    // -----------------------------------------------------------------------
    const Audio* FindAudio(const std::string& id) const
    {
        for (const auto& a : audio_array)
            if (a.id_Audio == id) return &a;
        return nullptr;
    }

    Audio* FindAudio(const std::string& id)
    {
        for (auto& a : audio_array)
            if (a.id_Audio == id) return &a;
        return nullptr;
    }

private:
    std::string m_currentMap;

    // Trim + ASCII-lowercase (bajty >= 0x80 - polskie znaki w Win-1250 - zostaja nietkniete,
    // bo tolower() na nich zalezy od locale i moze dac zle wyniki; obserwowana fragmentacja
    // ("Barbarzyńców" vs "barbarzyńców") dotyczy tylko pierwszej litery ASCII).
    static std::string NormalizeMapKey(const std::string& raw)
    {
        size_t start = 0, end = raw.size();
        while (start < end && (unsigned char)raw[start] <= ' ') start++;
        while (end > start && (unsigned char)raw[end - 1] <= ' ') end--;

        std::string out(raw, start, end - start);
        for (char& c : out)
        {
            unsigned char uc = (unsigned char)c;
            if (uc < 0x80)
                c = (char)tolower(uc);
        }
        return out;
    }

    // Stare INI mialy gole int ID (np. "32"). Nowy format to kompozytowy string ("woj_032").
    // Wszystkie dotychczas odblokowane ID pochodza z kampanii Woj, wiec migracja jest jednoznaczna.
    static std::string MigrateLegacyId(const std::string& val)
    {
        if (val.empty()) return val;

        bool allDigits = true;
        for (char c : val)
            if (!isdigit((unsigned char)c)) { allDigits = false; break; }

        if (!allDigits)
            return val; // juz kompozytowy format

        char buf[32];
        snprintf(buf, sizeof(buf), "woj_%03d", atoi(val.c_str()));
        return std::string(buf);
    }

    static void MergeUnlockedList(const char* val, std::vector<std::string>& out)
    {
        std::istringstream ss(val);
        char token[32];
        while (ss.getline(token, sizeof(token), ','))
        {
            if (token[0] == '\0') continue;
            std::string id = MigrateLegacyId(token);
            if (std::find(out.begin(), out.end(), id) == out.end())
                out.push_back(id);
        }
    }
};
