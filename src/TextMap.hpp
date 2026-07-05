#pragma once
#include <vector>
#include <string>

// Struktura mapowania: prefix tekstu dialogu na kod nagrania audio.
struct TextMapping {
    std::string id;       // kompozytowy kod "{kampania}_{lokalneId:03d}" np. "woj_032"
    char prefix[48];
    char mapFilter[64];   // nazwa mapy lub fragment; pusty/"*" = wszystkie
    char normPrefix[48];  // prefix z usuniętymi bajtami >0x7F, lowercase — do porównań encoding-neutral
};

extern std::vector<TextMapping> g_textMap;

// Callback logowania — ustaw raz w Start() żeby uniknąć zależności cyklicznej.
typedef void (*TextMapLogFn)(const char* msg);
void TextMap_SetLog(TextMapLogFn fn);

// Laduje plik text_map.txt do g_textMap. Zwraca liczbe zaladowanych wpisow.
int  LoadTextMap(const char* path);

// Szuka kodu nagrania pasujacego do tekstu dialogu (3-fazowe dopasowanie). Pusty string = brak.
std::string FindTextIdByContent(const char* text);

// Sprawdza, czy aktualna mapa H3 pasuje do filtru wpisu.
bool MapFilterMatches(const TextMapping& tm);

// Zwraca nazwe aktualnej mapy H3 (lub pusty string gdy niedostepna).
const char* GetCurrentMapName();

// Zwraca prefix tekstu dla danego kodu (z g_textMap). Pusty string gdy brak.
const char* GetTextPrefixById(const std::string& id);
