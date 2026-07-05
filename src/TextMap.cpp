#include "TextMap.hpp"
#include "H3Addresses.hpp"
#include "h3api/H3Defines/H3DataPointers.hpp"
#include "h3api/H3GameData/H3Main.hpp"
#include <fstream>
#include <cstring>
#include <cctype>
#include <cstdio>

using namespace h3;

std::vector<TextMapping> g_textMap;

static TextMapLogFn s_log = nullptr;
void TextMap_SetLog(TextMapLogFn fn) { s_log = fn; }

static void Log(const char* msg) { if (s_log) s_log(msg); }

//===================================================================================
//                           WCZYTYWANIE MAPY TEKSTOW
//===================================================================================

int LoadTextMap(const char* path)
{
    g_textMap.clear();
    std::ifstream file(path);
    if (!file.is_open())
        return 0;

    char line[256];
    while (file.getline(line, sizeof(line)))
    {
        if (line[0] == '#' || line[0] == '\0')
            continue;

        char* sep1 = strchr(line, '|');
        if (!sep1) continue;
        *sep1 = '\0';
        std::string id = line;

        const char* prefix = sep1 + 1;

        if (id.empty() || prefix[0] == '\0')
            continue;

        TextMapping tm;
        tm.id = id;

        char* sep2 = strchr(const_cast<char*>(prefix), '|');
        if (sep2)
        {
            int prefixLen = (int)(sep2 - prefix);
            if (prefixLen >= (int)sizeof(tm.prefix))
                prefixLen = (int)sizeof(tm.prefix) - 1;
            strncpy(tm.prefix, prefix, prefixLen);
            tm.prefix[prefixLen] = '\0';

            const char* mapF = sep2 + 1;
            strncpy(tm.mapFilter, mapF, sizeof(tm.mapFilter) - 1);
            tm.mapFilter[sizeof(tm.mapFilter) - 1] = '\0';
        }
        else
        {
            strncpy(tm.prefix, prefix, sizeof(tm.prefix) - 1);
            tm.prefix[sizeof(tm.prefix) - 1] = '\0';
            tm.mapFilter[0] = '\0';
        }

        int ni = 0;
        for (int k = 0; k < (int)sizeof(tm.prefix) - 1 && tm.prefix[k]; k++)
        {
            unsigned char c = (unsigned char)tm.prefix[k];
            if (c < 0x80 && ni < (int)sizeof(tm.normPrefix) - 1)
                tm.normPrefix[ni++] = (char)tolower(c);
        }
        tm.normPrefix[ni] = '\0';

        g_textMap.push_back(tm);
    }
    return (int)g_textMap.size();
}

//===================================================================================
//                           DOPASOWANIE TEKSTU DIALOGU
//===================================================================================

const char* GetCurrentMapName()
{
    __try
    {
        H3Main* game = P_Main();
        if (game)
        {
            PCHAR name = game->mapInfo.mapName.Begin();
            if (name && name[0] != '\0')
                return name;
        }
    }
    __except(EXCEPTION_EXECUTE_HANDLER) {}
    return "";
}

bool MapFilterMatches(const TextMapping& tm)
{
    if (tm.mapFilter[0] == '\0' || strcmp(tm.mapFilter, "*") == 0)
        return true;

    const char* mapName = GetCurrentMapName();
    if (mapName[0] == '\0')
        return true;

    char lowerMap[256];
    char lowerFilter[64];

    for (int i = 0; i < 255 && mapName[i]; i++)
        lowerMap[i] = (char)tolower((unsigned char)mapName[i]);
    lowerMap[255] = '\0';
    for (int i = (int)strlen(mapName); i < 256; i++) lowerMap[i] = '\0';

    for (int i = 0; i < 63 && tm.mapFilter[i]; i++)
        lowerFilter[i] = (char)tolower((unsigned char)tm.mapFilter[i]);
    lowerFilter[63] = '\0';
    for (int i = (int)strlen(tm.mapFilter); i < 64; i++) lowerFilter[i] = '\0';

    return (strstr(lowerMap, lowerFilter) != nullptr);
}

const char* GetTextPrefixById(const std::string& id)
{
    for (const auto& tm : g_textMap)
        if (tm.id == id) return tm.prefix;
    return "";
}

// LCS similarity: ile procent wzorca (pattern[0..patLen-1]) pokrywa tekst.
static int PrefixSimilarity(const char* text, const char* pattern, int patLen)
{
    if (patLen <= 0) return 100;
    if (patLen > 120) patLen = 120;

    static int dp[2][122];
    for (int j = 0; j <= patLen; j++) dp[0][j] = 0;

    int textLimit = patLen + 16;
    int i = 0;
    for (; i < textLimit && text[i] != '\0'; i++)
    {
        int row  = (i + 1) & 1;
        int prev = i & 1;
        dp[row][0] = 0;
        for (int j = 1; j <= patLen; j++)
        {
            if (text[i] == pattern[j - 1])
                dp[row][j] = dp[prev][j - 1] + 1;
            else
                dp[row][j] = dp[prev][j] > dp[row][j - 1] ? dp[prev][j] : dp[row][j - 1];
        }
    }

    int lcs = dp[i & 1][patLen];
    return lcs * 100 / patLen;
}

std::string FindTextIdByContent(const char* text)
{
    if (!text || !*text)
        return "";

    // Faza 1: dokladne dopasowanie prefiksu
    for (const auto& tm : g_textMap)
    {
        int prefixLen = (int)strlen(tm.prefix);
        if (prefixLen > 0 && strncmp(text, tm.prefix, prefixLen) == 0 && MapFilterMatches(tm))
            return tm.id;
    }

    // Faza 2: rozmyte dopasowanie LCS
    std::string bestId;
    int bestScore   = TextMatch::FUZZY_THRESHOLD - 1;
    const char* bestPrefix = "";
    for (const auto& tm : g_textMap)
    {
        int prefixLen = (int)strlen(tm.prefix);
        if (prefixLen < TextMatch::FUZZY_MIN_LEN) continue;
        if (!MapFilterMatches(tm)) continue;

        int score = PrefixSimilarity(text, tm.prefix, prefixLen);
        if (score > bestScore)
        {
            bestScore  = score;
            bestId     = tm.id;
            bestPrefix = tm.prefix;
        }
    }

    if (!bestId.empty())
    {
        char buf[256];
        snprintf(buf, sizeof(buf), "[Match] Rozmyte ID=%s score=%d%% wzorzec='%.40s'", bestId.c_str(), bestScore, bestPrefix);
        Log(buf);
        return bestId;
    }

    // Faza 3: szkielet ASCII — odporny na rozne kodowania (Win-1250 vs UTF-8)
    char normText[200] = {};
    {
        int ni = 0;
        for (int i = 0; i < 199 && text[i]; i++)
        {
            unsigned char c = (unsigned char)text[i];
            if (c < 0x80)
                normText[ni++] = (char)tolower(c);
        }
    }

    // 3a: dokladne na normPrefix
    for (const auto& tm : g_textMap)
    {
        int normLen = (int)strlen(tm.normPrefix);
        if (normLen < TextMatch::NORM_LCS_MIN) continue;
        if (!MapFilterMatches(tm)) continue;
        if (strncmp(normText, tm.normPrefix, normLen) == 0)
        {
            char buf[256];
            snprintf(buf, sizeof(buf), "[Match] ASCII-backbone dokladne ID=%s norm='%.40s'", tm.id.c_str(), tm.normPrefix);
            Log(buf);
            return tm.id;
        }
    }

    // 3b: rozmyte na normPrefix
    std::string bestNormId;
    int bestNormScore = TextMatch::FUZZY_THRESHOLD - 1;
    const char* bestNormPrefix = "";
    for (const auto& tm : g_textMap)
    {
        int normLen = (int)strlen(tm.normPrefix);
        if (normLen < TextMatch::NORM_LCS_MIN) continue;
        if (!MapFilterMatches(tm)) continue;

        int score = PrefixSimilarity(normText, tm.normPrefix, normLen);
        if (score > bestNormScore)
        {
            bestNormScore  = score;
            bestNormId     = tm.id;
            bestNormPrefix = tm.normPrefix;
        }
    }

    if (!bestNormId.empty())
    {
        char buf[256];
        snprintf(buf, sizeof(buf), "[Match] ASCII-backbone rozmyte ID=%s score=%d%% norm='%.40s'",
                 bestNormId.c_str(), bestNormScore, bestNormPrefix);
        Log(buf);
    }

    return bestNormId;
}
